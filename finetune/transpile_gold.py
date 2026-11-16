"""
Translate the BIRD train gold SQL from SQLite to PostgreSQL and keep only
what provably means the same: every query is run on the original SQLite
database and, translated, on its birdtrain_<db_id> copy (as the read-only
role, like generated SQL), and the two results are compared.

    python finetune/transpile_gold.py <folder> [--databases a b ...] [--limit N]

<folder> as for import_bird_train.py; only databases in its manifest are
used. Writes finetune/data/bird_train_gold.json: per question the original
and translated SQL, which variant matched and, for the rest, why not.

sqlglot carries SQLite's semantics over in full, which makes unusual
PostgreSQL: NULLIF around every divisor, NULLS FIRST / LAST on every ORDER BY.
Two variants are therefore tried, the first that matches is kept:
- clean: plain division, PostgreSQL's default NULL ordering, LIKE;
- faithful: SQLite's NULLS LAST for descending order (but not its NULLS
  FIRST for ascending, see translate), ILIKE (SQLite's LIKE ignores ASCII
  case), CAST AS REAL -> double precision (SQLite REAL is 8 bytes).
Both get the same name fixes: plain names lowercased as the import did,
other names matched case-insensitively to the stored ones, and a
double-quoted word that names nothing becomes a string, as SQLite reads it
("John" -> 'John').

Results are compared as sets of rows (BIRD's EX), numbers to 4 significant
digits (the clean variant keeps CAST AS REAL, a 4-byte float in
PostgreSQL), dates as ISO text. A query
whose SQLite result is empty is kept but flagged (empty: true): a match
then shows little.
"""

import argparse
import datetime
import json
import os
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from decimal import Decimal

import psycopg
import sqlglot
from sqlglot import exp

FINETUNE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(FINETUNE_DIR)
sys.path.append(os.path.join(REPO_DIR, "src"))

from database import get_connection
from sql_function_validator import validate_sql_functions
from sql_structural_validator import validate_sql_structure

from import_bird_train import DB_PREFIX, MANIFEST_PATH

OUTPUT_PATH = os.path.join(FINETUNE_DIR, "data", "bird_train_gold.json")
PLAIN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
SQLITE_TIMEOUT_S = 30
MAX_ROWS = 100_000


# ------------------------------------------------------------- translation

def catalog_names(conn):
    rows = conn.execute(
        "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'"
    ).fetchall()
    conn.rollback()
    names = {}
    for table, column in rows:
        names[table.lower()] = table
        names[column.lower()] = column
    return names


def defined_aliases(tree):
    aliases = {a.name.lower() for a in tree.find_all(exp.TableAlias) if a.name}
    aliases |= {a.alias.lower() for a in tree.find_all(exp.Alias) if a.alias}
    return aliases


def fix_names(tree, names):
    aliases = defined_aliases(tree)
    for node in list(tree.find_all(exp.Identifier)):
        name = node.name
        known = name.lower() in names or name.lower() in aliases
        parent = node.parent
        if (node.quoted and not known and isinstance(parent, exp.Column)
                and parent.this is node and not parent.table):
            parent.replace(exp.Literal.string(name))
        elif PLAIN.fullmatch(name):
            node.set("this", name.lower())
            node.set("quoted", False)
        elif name.lower() in names:
            node.set("this", names[name.lower()])
            node.set("quoted", True)


def translate(sql, names, variant):
    tree = sqlglot.parse_one(sql, read="sqlite")
    fix_names(tree, names)
    if variant == "clean":
        for div in tree.find_all(exp.Div):
            div.set("safe", False)
        for ordered in tree.find_all(exp.Ordered):
            # PostgreSQL's default: NULLs last ascending, first descending.
            ordered.set("nulls_first", bool(ordered.args.get("desc")))
    else:
        for ordered in tree.find_all(exp.Ordered):
            # SQLite's NULLS LAST for descending ("the highest") is kept. Its
            # NULLS FIRST for ascending is not: there a NULL row comes out as
            # "the shortest / oldest", a gold query defect, so such a query
            # no longer matches and is left out.
            if not ordered.args.get("desc"):
                ordered.set("nulls_first", False)
        for like in list(tree.find_all(exp.Like)):
            like.replace(exp.ILike(this=like.this, expression=like.expression))
        for cast in tree.find_all(exp.Cast):
            if cast.to.this == exp.DataType.Type.FLOAT:
                cast.set("to", exp.DataType.build("DOUBLE PRECISION"))
    return tree.sql(dialect="postgres")


# --------------------------------------------------------------- execution

def run_sqlite(con, sql):
    deadline = time.time() + SQLITE_TIMEOUT_S
    con.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 10_000)
    try:
        return con.execute(sql).fetchmany(MAX_ROWS + 1)
    finally:
        con.set_progress_handler(None, 0)


def run_postgres(conn, sql):
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchmany(MAX_ROWS + 1)
    finally:
        conn.rollback()


def normalize(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, Decimal)):
        number = float(value)
        if number.is_integer() and abs(number) < 1e15:
            return int(number)
        return float(f"{number:.4g}")
    if isinstance(value, datetime.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, (datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, datetime.timedelta):
        return float(f"{value.total_seconds() / 86400:.4g}")
    if isinstance(value, memoryview):
        return bytes(value)
    if isinstance(value, str):
        # A number stored as text in one database and as a number in the other.
        if re.fullmatch(r"-?\d+(\.\d+)?", value):
            return normalize(float(value))
        # SQLite text '2005-05-25 11:30:37.0' = PostgreSQL timestamp 11:30:37.
        stamp = re.fullmatch(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\.0+", value)
        return stamp.group(1) if stamp else value
    return value


def as_set(rows):
    return {tuple(normalize(v) for v in row) for row in rows}


def error_text(exc):
    return str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__


def check(question, con, conn, names):
    entry = {"db_id": question["db_id"], "question": question["question"],
             "evidence": question["evidence"], "sqlite_sql": question["SQL"]}
    try:
        expected = run_sqlite(con, question["SQL"])
    except sqlite3.OperationalError as exc:
        entry["status"] = "sqlite_timeout" if "interrupted" in str(exc) else "sqlite_error"
        entry["error"] = error_text(exc)
        return entry
    except sqlite3.Error as exc:
        entry["status"], entry["error"] = "sqlite_error", error_text(exc)
        return entry
    if len(expected) > MAX_ROWS:
        entry["status"] = "too_many_rows"
        return entry
    entry["empty"] = not expected
    expected_set = as_set(expected)

    last = None
    for variant in ("clean", "faithful"):
        try:
            sql = translate(question["SQL"], names, variant)
        except sqlglot.errors.SqlglotError as exc:
            last = {"status": "transpile_error", "error": error_text(exc)}
            continue
        try:
            got = run_postgres(conn, sql)
        except psycopg.errors.QueryCanceled as exc:
            last = {"status": "pg_timeout", "sql": sql, "error": error_text(exc)}
            continue
        except psycopg.Error as exc:
            last = {"status": "pg_error", "sql": sql, "error": error_text(exc)}
            continue
        if as_set(got) == expected_set:
            entry.update({"status": "ok", "variant": variant, "sql": sql})
            for validate in (validate_sql_structure, validate_sql_functions):
                valid, message = validate(sql)
                if not valid:
                    entry.update({"status": "validator_rejected", "error": message})
                    break
            return entry
        last = {"status": "mismatch", "sql": sql,
                "expected_rows": len(expected), "got_rows": len(got)}
    entry.update(last)
    return entry


def error_kind(entry):
    """A short class of a failure for the summary."""
    text = entry.get("error", "")
    for pattern, kind in [
        (r"function (\w+)\(", "function {}"),
        (r"operator does not exist: (\w+(?: \w+)?) (\S+)", "operator {} {}"),
        (r'column "?(.+?)"? does not exist', "unknown column"),
        (r"relation .* does not exist", "unknown table"),
        (r"must appear in the GROUP BY", "GROUP BY rule"),
        (r"invalid input syntax for type (\w+)", "invalid input for {}"),
        (r"division by zero", "division by zero"),
    ]:
        match = re.search(pattern, text)
        if match:
            return kind.format(*match.groups())
    return text[:60]


def main():
    parser = argparse.ArgumentParser(description="BIRD train gold SQL átírása PostgreSQL-re, futtatásos ellenőrzéssel")
    parser.add_argument("folder", help="a kicsomagolt train.zip mappája")
    parser.add_argument("--databases", nargs="+", help="csak ezek (alapértelmezés: minden importált)")
    parser.add_argument("--limit", type=int, help="adatbázisonként legfeljebb ennyi kérdés (próbához)")
    args = parser.parse_args()

    with open(MANIFEST_PATH, encoding="utf-8") as file:
        imported = set(json.load(file)["databases"])
    with open(os.path.join(args.folder, "train", "train.json"), encoding="utf-8") as file:
        questions = json.load(file)
    for i, q in enumerate(questions):
        q["id"] = i

    wanted = set(args.databases) if args.databases else imported
    missing = wanted - imported
    if missing:
        sys.exit(f"Nincs importálva: {', '.join(sorted(missing))}")

    by_db = defaultdict(list)
    for q in questions:
        if q["db_id"] in wanted:
            by_db[q["db_id"]].append(q)

    results = []
    for db_id in sorted(by_db):
        started = time.time()
        path = os.path.join(args.folder, "train_databases", db_id, db_id + ".sqlite")
        con = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
        con.text_factory = lambda raw: raw.decode("utf-8", errors="replace")
        conn = get_connection(DB_PREFIX + db_id)
        names = catalog_names(conn)
        items = by_db[db_id][:args.limit] if args.limit else by_db[db_id]
        db_results = []
        for q in items:
            entry = check(q, con, conn, names)
            db_results.append({"id": q["id"], **entry})
        con.close()
        conn.close()
        counts = Counter(r["status"] for r in db_results)
        print(f"{db_id}: {counts['ok']}/{len(db_results)} jó "
              f"({', '.join(f'{k} {v}' for k, v in counts.most_common() if k != 'ok')}) "
              f"{time.time() - started:.0f} s")
        results.extend(db_results)

    counts = Counter(r["status"] for r in results)
    variants = Counter(r["variant"] for r in results if r["status"] == "ok")
    kinds = Counter(error_kind(r) for r in results if r["status"] in ("pg_error", "sqlite_error"))
    summary = {
        "questions": len(results),
        "status": dict(counts.most_common()),
        "ok_variants": dict(variants),
        "ok_empty": sum(1 for r in results if r["status"] == "ok" and r.get("empty")),
        "error_kinds": dict(kinds.most_common(25)),
    }
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
        json.dump({"summary": summary, "questions": results}, file, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
