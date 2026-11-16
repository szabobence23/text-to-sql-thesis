"""
Import the BIRD train databases (SQLite) into the docker-compose PostgreSQL
server, one database per BIRD database (birdtrain_<db_id>), as material for
fine-tuning. They are not datasets (no test questions, nothing in
datasets/): the training data builder reads their schema text with
schema.get_schema and checks the transpiled gold SQL on them.

    python finetune/import_bird_train.py <folder> [--databases a b ...] [--max-mb 1000] [--recreate]

<folder> is the unpacked train.zip
(https://bird-bench.oss-cn-beijing.aliyuncs.com/train.zip, 2023-07) with
its inner train_databases.zip unpacked next to train/, so the databases are
<folder>/train_databases/<db>/<db>.sqlite.

Without --databases every database up to --max-mb is imported; EXCLUDED
ones never are. A database already imported (in the manifest) is skipped
unless --recreate; one that exists but is not in the manifest was left
half-built by a stopped run and is rebuilt.

Conventions follow the Mini-Dev PostgreSQL version (database/import_bird.py),
so the schema text looks like the one the model is tested on:
- Plain names (letters, digits, _) are lowercased, the rest kept as they
  are (schema.sql_identifier double-quotes them in the schema text):
  customerNumber -> customernumber, "Order Date" stays. SQLite names are
  case-insensitive, so lowercasing does not change what a query means.
- INTEGER -> bigint, REAL -> double precision, TEXT -> text, BLOB -> bytea.
  Unlike Mini-Dev (real): SQLite's REAL is 8 bytes, and in a 4-byte real
  column `rental_rate = 2.99` finds nothing, so many gold queries would not
  mean the same. SQLite does not enforce types: a column whose stored
  values do not fit its declared type becomes text (or double precision
  for fractions in an INTEGER column).
- DATE / DATETIME columns become date / timestamp when every value is an
  ISO date (YYYY-MM-DD) / date and time, otherwise text.
- Primary keys as declared, when the data allows (unique, not null).
- Foreign keys as declared, NOT VALID: SQLite does not enforce them and
  many BIRD databases have orphan rows; the relationship still shows in the
  schema text. Referenced columns that are unique in the data but have no
  constraint get a UNIQUE constraint first; an FK that cannot be made
  (columns not unique, types differ, unknown table) is skipped.
Every departure from the declaration is recorded in the manifest
finetune/data/bird_train_import.json, with row counts checked against
SQLite.
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from collections import defaultdict

import psycopg
from psycopg import sql as pgsql

FINETUNE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(FINETUNE_DIR)
sys.path.append(os.path.join(REPO_DIR, "database"))

from setup_dataset import READONLY_ROLE_SQL, psql, read

DB_PREFIX = "birdtrain_"
MANIFEST_PATH = os.path.join(FINETUNE_DIR, "data", "bird_train_import.json")
SOURCE_NOTE = "BIRD train (bird-bench.github.io, CC BY-SA 4.0), train.zip 2023-07"

# Never imported: training on them would leak into a test set.
EXCLUDED = {
    "works_cycles": "AdventureWorks OLTP: the same schema as the adventureworks test dataset",
}

ADMIN = {
    "host": os.getenv("TEXT2SQL_DB_HOST", "localhost"),
    "port": int(os.getenv("TEXT2SQL_DB_PORT", "5432")),
    "user": os.getenv("TEXT2SQL_ADMIN_USER", "postgres"),
    "password": os.getenv("TEXT2SQL_ADMIN_PASSWORD", "postgres"),
}

PLAIN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
ISO_DATE = r"^\d{4}-\d{2}-\d{2}$"
ISO_TIMESTAMP = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2}(\.\d+)?)?$"
FLOAT_TYPE = "double precision"  # for SQLite REAL (8 bytes), see the docstring
KINDS = ("integer", "real", "text", "blob")
PROFILE_CHUNK = 100  # columns per profiling query (SQLite allows 2000 result columns)


def pg_name(name):
    return name.lower() if PLAIN.fullmatch(name) else name


def sqlite_quote(name):
    return '"' + name.replace('"', '""') + '"'


def ident(name):
    return pgsql.Identifier(name)


def idents(names):
    return pgsql.SQL(", ").join(ident(n) for n in names)


class Decoder:
    """SQLite text_factory: UTF-8, counting the values that are not."""

    def __init__(self):
        self.errors = 0

    def __call__(self, raw):
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            self.errors += 1
            return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------- SQLite side

def read_catalog(con):
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]
    catalog = {}
    for table in tables:
        info = con.execute(f"PRAGMA table_info({sqlite_quote(table)})").fetchall()
        columns = [{"name": r[1], "declared": (r[2] or "").upper()} for r in info]
        primary_key = [r[1] for r in sorted((r for r in info if r[5]), key=lambda r: r[5])]
        groups = defaultdict(list)
        for r in con.execute(f"PRAGMA foreign_key_list({sqlite_quote(table)})"):
            groups[r[0]].append({"table": r[2], "from": r[3], "to": r[4]})
        catalog[table] = {
            "columns": columns,
            "primary_key": primary_key,
            "foreign_keys": list(groups.values()),
        }
    return catalog


def profile(con, table, columns):
    """Row count and, per column, how many stored values are of each SQLite type."""
    rows = con.execute(f"SELECT count(*) FROM {sqlite_quote(table)}").fetchone()[0]
    counts = {}
    for start in range(0, len(columns), PROFILE_CHUNK):
        chunk = columns[start:start + PROFILE_CHUNK]
        parts = [
            f"coalesce(sum(typeof({sqlite_quote(c['name'])}) = '{kind}'), 0)"
            for c in chunk for kind in KINDS
        ]
        values = con.execute(f"SELECT {', '.join(parts)} FROM {sqlite_quote(table)}").fetchone()
        for i, c in enumerate(chunk):
            counts[c["name"]] = dict(zip(KINDS, values[i * 4:i * 4 + 4]))
    return rows, counts


def affinity(declared):
    # SQLite's type affinity rules (sqlite.org/datatype3.html, 3.1).
    if "INT" in declared:
        return "integer"
    if any(k in declared for k in ("CHAR", "CLOB", "TEXT")):
        return "text"
    if "BLOB" in declared or not declared:
        return "blob"
    if any(k in declared for k in ("REAL", "FLOA", "DOUB")):
        return "real"
    return "numeric"


def decide_type(declared, counts):
    """(PostgreSQL type, note) from the declared type and the stored values.
    'date?' / 'timestamp?' = load as text, decide after the load."""
    ints, reals, texts, blobs = (counts[k] for k in KINDS)
    if blobs:
        if ints or reals or texts:
            return "text", "BLOB values mixed with others"
        return "bytea", None
    if "DATE" in declared or "TIME" in declared:
        if not ints and not reals:
            return ("timestamp?" if "TIME" in declared else "date?"), None
        if texts:
            return "text", f"{declared} column with numbers and text"
        return ("bigint" if not reals else FLOAT_TYPE), f"{declared} column holding numbers"
    kind = affinity(declared)
    if kind == "integer":
        if texts:
            return "text", f"{texts} text values in an {declared} column"
        if reals:
            return FLOAT_TYPE, f"{reals} fractional values in an {declared} column"
        return "bigint", None
    if kind in ("real", "numeric"):
        if texts:
            return "text", f"{texts} text values in a {declared} column"
        if kind == "numeric" and not reals:
            return "bigint", None
        return FLOAT_TYPE, None
    if kind == "blob":
        if ints or reals or texts:
            return "text", f"non-BLOB values in a {declared or 'untyped'} column"
        return "bytea", None
    return "text", None


def sqlite_float_text(value):
    # How SQLite casts a REAL to TEXT ("%!.15g"): 100.0 -> '100.0'.
    text = f"{value:.15g}"
    if not any(c in text for c in ".einn"):
        text += ".0"
    return text


def converter(pg_type, stats):
    def to_text(v):
        if v is None:
            return None
        if isinstance(v, bytes):
            v = v.decode("utf-8", errors="replace")
        elif isinstance(v, float):
            v = sqlite_float_text(v)
        elif not isinstance(v, str):
            v = str(v)
        if "\x00" in v:
            stats["nul_removed"] += 1
            v = v.replace("\x00", "")
        return v

    if pg_type == "bigint":
        return lambda v: v
    if pg_type == FLOAT_TYPE:
        return lambda v: None if v is None else float(v)
    if pg_type == "bytea":
        return lambda v: v
    return to_text


# ------------------------------------------------------------ PostgreSQL side

def database_exists(db):
    with psycopg.connect(dbname="postgres", autocommit=True, **ADMIN) as conn:
        return conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db,)).fetchone() is not None


def recreate_database(db):
    with psycopg.connect(dbname="postgres", autocommit=True, **ADMIN) as conn:
        conn.execute(pgsql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(ident(db)))
        conn.execute(pgsql.SQL("CREATE DATABASE {}").format(ident(db)))


def decide_temporal(conn, table, column, guess):
    """date / timestamp when every value is ISO and valid, else text (with a note)."""
    c = ident(column)
    query = pgsql.SQL(
        "SELECT count({c}), "
        "count(*) FILTER (WHERE {c} IS NOT NULL AND NOT ({c} ~ %s AND pg_input_is_valid({c}, 'date'))), "
        "count(*) FILTER (WHERE {c} IS NOT NULL AND NOT ("
        "  ({c} ~ %s AND pg_input_is_valid({c}, 'date')) OR "
        "  ({c} ~ %s AND pg_input_is_valid({c}, 'timestamp')))), "
        "min({c}) FILTER (WHERE {c} IS NOT NULL AND NOT ("
        "  ({c} ~ %s AND pg_input_is_valid({c}, 'date')) OR "
        "  ({c} ~ %s AND pg_input_is_valid({c}, 'timestamp')))) "
        "FROM {t}"
    ).format(c=c, t=ident(table))
    filled, not_date, not_timestamp, example = conn.execute(
        query, (ISO_DATE, ISO_DATE, ISO_TIMESTAMP, ISO_DATE, ISO_TIMESTAMP)
    ).fetchone()
    if filled == 0:
        return guess.rstrip("?"), "no values"
    if not_date == 0:
        return "date", None
    if not_timestamp == 0:
        return "timestamp", None
    return "text", f"{not_timestamp} of {filled} values not ISO dates, e.g. {example!r}"


def unique_constraint_exists(conn, table, columns):
    rows = conn.execute(
        """
        SELECT array_agg(a.attname ORDER BY a.attname)
        FROM pg_constraint con
        JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = ANY (con.conkey)
        WHERE con.conrelid = %s::regclass AND con.contype IN ('p', 'u')
        GROUP BY con.oid
        """,
        (pgsql.Identifier(table).as_string(conn),),
    ).fetchall()
    return sorted(columns) in [r[0] for r in rows]


def try_ddl(conn, statement):
    """Run one DDL statement in its own transaction; the error text, or None."""
    try:
        with conn.transaction():
            conn.execute(statement)
        return None
    except psycopg.Error as exc:
        return str(exc).strip().splitlines()[0]


def resolve(names, wanted):
    """SQLite names are case-insensitive: the actual name for a wanted one, or None."""
    by_lower = {n.lower(): n for n in names}
    return by_lower.get(wanted.lower()) if wanted is not None else None


def import_database(db_id, path, reserved_words):
    db = DB_PREFIX + db_id
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", db):
        sys.exit(f"Érvénytelen adatbázisnév: {db}")

    started = time.time()
    decoder = Decoder()
    stats = {"nul_removed": 0}
    con = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    con.text_factory = decoder
    catalog = read_catalog(con)

    # Name mapping and collision check (lowercasing can merge two names).
    table_names = {t: pg_name(t) for t in catalog}
    if len(set(table_names.values())) != len(table_names):
        sys.exit(f"{db_id}: két tábla neve kisbetűsítve egybeesik")
    for t, info in catalog.items():
        mapped = [pg_name(c["name"]) for c in info["columns"]]
        if len(set(mapped)) != len(mapped):
            sys.exit(f"{db_id}.{t}: két oszlop neve kisbetűsítve egybeesik")

    recreate_database(db)
    report = {"source": SOURCE_NOTE, "source_mb": round(os.path.getsize(path) / 1e6, 1), "tables": {}}

    with psycopg.connect(dbname=db, autocommit=True, **ADMIN) as conn:
        # 1. Tables and data.
        for t, info in catalog.items():
            pt = table_names[t]
            rows, counts = profile(con, t, info["columns"])
            columns = {}
            for c in info["columns"]:
                pg_type, note = decide_type(c["declared"], counts[c["name"]])
                columns[pg_name(c["name"])] = {
                    "source": c["name"], "declared": c["declared"], "type": pg_type, "note": note,
                }
            load_types = {n: ("text" if col["type"].endswith("?") else col["type"]) for n, col in columns.items()}
            conn.execute(pgsql.SQL("CREATE TABLE {} ({})").format(
                ident(pt),
                pgsql.SQL(", ").join(
                    pgsql.SQL("{} {}").format(ident(n), pgsql.SQL(load_types[n])) for n in columns
                ),
            ))
            convert = [converter(load_types[n], stats) for n in columns]
            source_cols = ", ".join(sqlite_quote(c["name"]) for c in info["columns"])
            with conn.transaction():
                with conn.cursor().copy(pgsql.SQL("COPY {} ({}) FROM STDIN").format(
                    ident(pt), idents(columns)
                )) as copy:
                    for row in con.execute(f"SELECT {source_cols} FROM {sqlite_quote(t)}"):
                        copy.write_row([f(v) for f, v in zip(convert, row)])

            # 2. Dates: decided on the loaded text.
            changes = []
            for n, col in columns.items():
                if col["type"].endswith("?"):
                    col["type"], col["note"] = decide_temporal(conn, pt, n, col["type"])
                    if col["type"] != "text":
                        changes.append(pgsql.SQL("ALTER COLUMN {c} TYPE {ty} USING {c}::{ty}").format(
                            c=ident(n), ty=pgsql.SQL(col["type"])))
            if changes:
                conn.execute(pgsql.SQL("ALTER TABLE {} {}").format(ident(pt), pgsql.SQL(", ").join(changes)))

            loaded = conn.execute(pgsql.SQL("SELECT count(*) FROM {}").format(ident(pt))).fetchone()[0]
            if loaded != rows:
                sys.exit(f"{db_id}.{t}: {rows} sor helyett {loaded} töltődött be")

            # 3. Primary key.
            primary_key = [pg_name(c) for c in info["primary_key"]]
            pk_error = None
            if primary_key:
                pk_error = try_ddl(conn, pgsql.SQL("ALTER TABLE {} ADD PRIMARY KEY ({})").format(
                    ident(pt), idents(primary_key)))

            report["tables"][pt] = {
                "source": t,
                "rows": rows,
                "primary_key": primary_key or None,
                "primary_key_error": pk_error,
                "columns": {n: {k: v for k, v in col.items() if v is not None} for n, col in columns.items()},
            }
            print(f"  {pt}: {rows} sor, {len(columns)} oszlop")

        # 4. Foreign keys (after every table exists).
        foreign_keys, seen = [], set()
        for t, info in catalog.items():
            for group in info["foreign_keys"]:
                entry = {"from_table": table_names[t], "declared": group}
                parent = resolve(catalog, group[0]["table"])
                child_cols = [resolve([c["name"] for c in info["columns"]], g["from"]) for g in group]
                if parent is None:
                    entry["skipped"] = f"unknown table {group[0]['table']!r}"
                    foreign_keys.append(entry)
                    continue
                parent_names = [c["name"] for c in catalog[parent]["columns"]]
                if all(g["to"] is None for g in group):
                    parent_cols = catalog[parent]["primary_key"]
                else:
                    parent_cols = [resolve(parent_names, g["to"]) for g in group]
                if None in child_cols or None in parent_cols or len(parent_cols) != len(child_cols):
                    entry["skipped"] = "unknown or missing columns"
                    foreign_keys.append(entry)
                    continue
                child = [pg_name(c) for c in child_cols]
                target = [pg_name(c) for c in parent_cols]
                key = (table_names[t], tuple(child), table_names[parent], tuple(target))
                if key in seen:
                    continue
                seen.add(key)
                entry.update({"columns": child, "to_table": table_names[parent], "to_columns": target})
                if not unique_constraint_exists(conn, table_names[parent], target):
                    error = try_ddl(conn, pgsql.SQL("ALTER TABLE {} ADD UNIQUE ({})").format(
                        ident(table_names[parent]), idents(target)))
                    if error:
                        entry["skipped"] = f"referenced columns not unique: {error}"
                        foreign_keys.append(entry)
                        continue
                    entry["unique_added"] = True
                error = try_ddl(conn, pgsql.SQL("ALTER TABLE {} ADD FOREIGN KEY ({}) REFERENCES {} ({}) NOT VALID").format(
                    ident(table_names[t]), idents(child), ident(table_names[parent]), idents(target)))
                if error:
                    entry["skipped"] = error
                foreign_keys.append(entry)
        report["foreign_keys"] = foreign_keys

        conn.execute("ANALYZE")

    con.close()
    psql(db, read(READONLY_ROLE_SQL), variables={"db_name": db})

    names = [n for t in report["tables"].values() for n in t["columns"]] + list(report["tables"])
    report.update({
        "database": db,
        "rows": sum(t["rows"] for t in report["tables"].values()),
        "renamed": sum(1 for n in table_names.values() if n not in catalog)
        + sum(1 for t in report["tables"].values() for n, c in t["columns"].items() if n != c["source"]),
        "reserved_word_names": sorted({n for n in names if n in reserved_words}),
        "decode_errors": decoder.errors,
        "nul_removed": stats["nul_removed"],
        "seconds": round(time.time() - started, 1),
    })
    return report


def load_manifest():
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, encoding="utf-8") as file:
            return json.load(file)
    return {"source": SOURCE_NOTE, "excluded": EXCLUDED, "databases": {}}


def save_manifest(manifest):
    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    manifest["excluded"] = EXCLUDED
    manifest["databases"] = dict(sorted(manifest["databases"].items()))
    with open(MANIFEST_PATH, "w", encoding="utf-8") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=1)


def summary_line(db_id, r):
    columns = [c for t in r["tables"].values() for c in t["columns"].values()]
    notes = sum(1 for c in columns if "note" in c and c["note"] != "no values")
    fk_ok = sum(1 for f in r["foreign_keys"] if "skipped" not in f)
    pk_fail = sum(1 for t in r["tables"].values() if t["primary_key_error"])
    return (f"{db_id}: {len(r['tables'])} tábla, {r['rows']} sor, FK {fk_ok}/{len(r['foreign_keys'])}, "
            f"PK-hiba {pk_fail}, típuseltérés {notes}, {r['seconds']} s")


def main():
    parser = argparse.ArgumentParser(description="BIRD train SQLite adatbázisok importálása PostgreSQL-be")
    parser.add_argument("folder", help="a kicsomagolt train.zip mappája (benne train_databases/)")
    parser.add_argument("--databases", nargs="+", help="csak ezek (alapértelmezés: mind, --max-mb alatt)")
    parser.add_argument("--max-mb", type=float, default=1000, help="ennél nagyobb SQLite fájlt kihagy (alapértelmezés 1000)")
    parser.add_argument("--recreate", action="store_true", help="a már importáltakat is újraépíti")
    args = parser.parse_args()

    db_root = os.path.join(args.folder, "train_databases")
    available = sorted(d for d in os.listdir(db_root)
                       if os.path.exists(os.path.join(db_root, d, d + ".sqlite")))
    unknown = set(args.databases or []) - set(available)
    if unknown:
        sys.exit(f"Ismeretlen adatbázis: {', '.join(sorted(unknown))}")

    manifest = load_manifest()
    with psycopg.connect(dbname="postgres", **ADMIN) as conn:
        reserved = {r[0] for r in conn.execute("SELECT word FROM pg_get_keywords() WHERE catcode = 'R'")}

    for db_id in args.databases or available:
        path = os.path.join(db_root, db_id, db_id + ".sqlite")
        size_mb = os.path.getsize(path) / 1e6
        if db_id in EXCLUDED:
            print(f"{db_id}: kihagyva ({EXCLUDED[db_id]})")
            continue
        if not args.databases and size_mb > args.max_mb:
            print(f"{db_id}: kihagyva ({size_mb:.0f} MB > {args.max_mb:.0f} MB)")
            continue
        done = db_id in manifest["databases"] and database_exists(DB_PREFIX + db_id)
        if done and not args.recreate:
            print(f"{db_id}: már importálva")
            continue
        print(f"{db_id} ({size_mb:.0f} MB) importálása...")
        manifest["databases"][db_id] = import_database(db_id, path, reserved)
        save_manifest(manifest)
        print(summary_line(db_id, manifest["databases"][db_id]))


if __name__ == "__main__":
    main()
