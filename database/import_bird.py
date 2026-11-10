"""
Import the BIRD Mini-Dev benchmark (PostgreSQL version) as one dataset per
database: datasets/bird_<db_id>/ with dataset.json, schema.sql, import.sql,
test_cases/en.json and excluded_cases.json, and the data as CSV files in
data/ (gitignored).

    python database/import_bird.py <minidev folder> [--keep-staging]

<minidev folder> is the unpacked minidev.zip
(https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip, 2024-06),
holding MINIDEV/ (questions, table lists) and MINIDEV_postgresql/BIRD_dev.sql.

1. BIRD_dev.sql (all 11 databases, 75 tables, one pg_dump) is loaded into
   a staging database in the container; its OWNER TO statements name a
   role that does not exist here and are dropped.
2. The dump is split by dev_tables.json: per database the CREATE TABLE
   statements, primary keys, unique indexes and foreign keys as the dump
   has them (sequences and column defaults are left out: nothing is ever
   written), and every table exported from staging to CSV.
3. The questions of mini_dev_postgresql.json, with their evidence and
   difficulty, become test_cases/en.json (BIRD is English only). The
   file holds two questions twice (financial #137, #138); each is kept once.
4. setup_dataset.py builds every database, then every ground truth is run
   as the read-only role: one that fails, exceeds the role's 10 s timeout
   or cannot be parsed is moved to excluded_cases.json with the reason, as
   the evaluator stops on a broken ground truth.

The datasets are evaluation-only ("listed": false): the web UI and the MCP
server do not offer them.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict

DATABASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(DATABASE_DIR)
sys.path.append(os.path.join(REPO_DIR, "src"))

from setup_dataset import CONTAINER, psql

STAGING_DB = "bird_minidev_staging"
DATASETS_DIR = os.path.join(REPO_DIR, "datasets")
SOURCE_NOTE = (
    "BIRD Mini-Dev (bird-bench.github.io, CC BY-SA 4.0), PostgreSQL version "
    "(minidev.zip, MINIDEV_postgresql/BIRD_dev.sql)"
)

# label, summary per UI language; only shown if a dataset is ever listed.
DESCRIPTIONS = {
    "california_schools": ("California schools", "Kaliforniai iskolák",
                           "schools, free meal (FRPM) figures, SAT scores",
                           "iskolák, ingyenes étkezés (FRPM) adatai, SAT-eredmények"),
    "card_games": ("Card games", "Kártyajáték",
                   "Magic: The Gathering cards, sets, legalities, rulings, translations",
                   "Magic: The Gathering kártyák, kiadások, legalitás, szabályok, fordítások"),
    "codebase_community": ("Codebase community", "Kérdés-válasz közösség",
                           "Stack Exchange posts, users, comments, votes, badges",
                           "Stack Exchange bejegyzések, felhasználók, kommentek, szavazatok, jelvények"),
    "debit_card_specializing": ("Debit cards", "Bankkártyák",
                                "gas station card customers, transactions, monthly consumption",
                                "benzinkúti kártyás ügyfelek, tranzakciók, havi fogyasztás"),
    "european_football_2": ("European football", "Európai labdarúgás",
                            "matches, leagues, teams and players with attributes",
                            "mérkőzések, ligák, csapatok és játékosok jellemzőkkel"),
    "financial": ("Financial", "Bank",
                  "Czech bank: accounts, clients, loans, cards, transactions",
                  "cseh bank: számlák, ügyfelek, hitelek, kártyák, tranzakciók"),
    "formula_1": ("Formula 1 (BIRD)", "Forma–1 (BIRD)",
                  "races, drivers, constructors, results, standings, lap times",
                  "futamok, versenyzők, csapatok, eredmények, pontversenyek, köridők"),
    "student_club": ("Student club", "Diákklub",
                     "events, members, budget, expenses, income",
                     "események, tagok, költségvetés, kiadások, bevételek"),
    "superhero": ("Superheroes", "Szuperhősök",
                  "heroes with powers, attributes, publishers",
                  "hősök képességekkel, tulajdonságokkal, kiadókkal"),
    "thrombosis_prediction": ("Thrombosis prediction", "Trombózis-előrejelzés",
                              "patients, examinations and laboratory results",
                              "betegek, vizsgálatok és laboreredmények"),
    "toxicology": ("Toxicology", "Toxikológia",
                   "molecules, atoms, bonds and their connections",
                   "molekulák, atomok, kötések és kapcsolataik"),
}

TABLE_REF = re.compile(r'public\.(?:"([^"]+)"|(\w+))')
# Statements of the dump that are not needed: nothing is ever written.
SKIPPED = re.compile(
    r"(SET |SELECT pg_catalog\.set(_config|val)\(|CREATE SEQUENCE |ALTER SEQUENCE |"
    r"ALTER TABLE ONLY public\.\S+ ALTER COLUMN \S+ SET DEFAULT )"
)


def table_of(statement, after):
    """The table named after `after` in a statement, and its spelling."""
    match = TABLE_REF.search(statement, statement.index(after))
    return (match.group(1) or match.group(2)).lower(), match.group(0)


def parse_dump(path):
    """
    Per table: its spelling in SQL, CREATE TABLE, and the primary keys,
    indexes and foreign keys (with the referenced table) of the dump.
    Fails on any statement it does not expect, so nothing unreviewed
    reaches the database.
    """
    tables = {}
    keys = defaultdict(list)
    indexes = defaultdict(list)
    foreign_keys = defaultdict(list)
    statement = ""
    in_copy = False

    with open(path, encoding="utf-8") as file:
        for line in file:
            if in_copy:
                in_copy = line.rstrip("\n") != "\\."
                continue
            stripped = line.strip()
            if not statement and (not stripped or stripped.startswith("--")):
                continue
            if not statement and stripped.startswith("COPY public."):
                in_copy = True
                continue
            if stripped.startswith("\\"):
                raise ValueError(f"psql meta-command in the dump: {stripped[:80]}")
            statement += line
            if not stripped.endswith(";"):
                continue

            text = statement.strip()
            flat = " ".join(text.split())
            statement = ""
            if SKIPPED.match(flat) or flat.endswith("OWNER TO xiaolongli;"):
                continue
            if flat.startswith("CREATE TABLE public."):
                name, ref = table_of(flat, "CREATE TABLE")
                tables[name] = {"ref": ref, "create": text}
            elif flat.startswith("ALTER TABLE ONLY public.") and " PRIMARY KEY " in flat:
                keys[table_of(flat, "ALTER TABLE")[0]].append(text)
            elif flat.startswith("ALTER TABLE ONLY public.") and " FOREIGN KEY " in flat:
                target = table_of(flat, "REFERENCES")[0]
                foreign_keys[table_of(flat, "ALTER TABLE")[0]].append((target, text))
            elif re.match(r"CREATE (UNIQUE )?INDEX \S+ ON public\.", flat):
                indexes[table_of(flat, " ON ")[0]].append(text)
            else:
                raise ValueError(f"Unexpected statement in the dump: {flat[:120]}")

    return tables, keys, indexes, foreign_keys


def load_order(names, foreign_keys):
    """Referenced tables before the tables that reference them."""
    order, done = [], set()

    def visit(name, path):
        if name in done:
            return
        if name in path:
            raise ValueError(f"Foreign key cycle through {name}")
        for target, _ in foreign_keys[name]:
            if target != name:
                visit(target, path | {name})
        done.add(name)
        order.append(name)

    for name in names:
        visit(name, set())
    return order


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        file.write(text)


def load_staging(dump_path, reload):
    exists = psql("postgres", f"SELECT 1 FROM pg_database WHERE datname = '{STAGING_DB}';", capture=True)
    if exists and not reload:
        print(f"{STAGING_DB} already loaded.")
        return
    print(f"Loading the dump into {STAGING_DB}...")
    psql("postgres", f"DROP DATABASE IF EXISTS {STAGING_DB}; CREATE DATABASE {STAGING_DB};")
    subprocess.run(["docker", "cp", dump_path, f"{CONTAINER}:/tmp/bird_dev.sql"], check=True)
    subprocess.run(
        ["docker", "exec", CONTAINER, "sh", "-c",
         "grep -v 'OWNER TO xiaolongli' /tmp/bird_dev.sql | "
         f"psql -U postgres -d {STAGING_DB} -v ON_ERROR_STOP=1 -q && rm /tmp/bird_dev.sql"],
        check=True,
    )


def write_dataset(db_id, table_names, dump, questions):
    tables, keys, indexes, foreign_keys = dump
    name = f"bird_{db_id}"
    folder = os.path.join(DATASETS_DIR, name)

    for table in table_names:
        if table not in tables:
            raise ValueError(f"{db_id}: table {table} is not in the dump")
        for target, _ in foreign_keys[table]:
            if target not in table_names:
                raise ValueError(f"{db_id}: {table} references {target} of another database")

    order = load_order(table_names, foreign_keys)

    schema = [f"-- {SOURCE_NOTE}, database {db_id}.", "-- Written by database/import_bird.py.", ""]
    schema += [tables[t]["create"] + "\n" for t in table_names]
    schema += [k for t in table_names for k in keys[t]]
    schema += [i for t in table_names for i in indexes[t]]
    schema += [fk for t in table_names for _, fk in foreign_keys[t]]
    write(os.path.join(folder, "schema.sql"), "\n".join(schema) + "\n")

    load = ["-- Load order follows the foreign keys. Written by database/import_bird.py.", ""]
    for table in order:
        load += [
            f"\\echo 'Importing {table}...'",
            f"COPY {tables[table]['ref']} FROM '/datasets/{name}/data/{table}.csv'",
            "WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');",
            "",
        ]
    load.append("ANALYZE;")
    write(os.path.join(folder, "import.sql"), "\n".join(load) + "\n")

    # /datasets is mounted read-only in the container: the CSV comes out
    # on psql's stdout and is written here.
    os.makedirs(os.path.join(folder, "data"), exist_ok=True)
    for table in table_names:
        with open(os.path.join(folder, "data", f"{table}.csv"), "wb") as out:
            subprocess.run(
                ["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", STAGING_DB,
                 "-v", "ON_ERROR_STOP=1", "-q", "-c",
                 f"COPY (SELECT * FROM {tables[table]['ref']}) TO STDOUT WITH (FORMAT csv, HEADER true)"],
                stdout=out,
                check=True,
            )

    label_en, label_hu, summary_en, summary_hu = DESCRIPTIONS[db_id]
    count = f"{len(table_names)} tables"
    config = {
        "name": name,
        "label": {"hu": f"BIRD: {label_hu}", "en": f"BIRD: {label_en}"},
        "summary": {
            "hu": f"{summary_hu} ({len(table_names)} tábla; BIRD Mini-Dev, csak kiértékeléshez)",
            "en": f"{summary_en} ({count}; BIRD Mini-Dev, evaluation only)",
        },
        "db_name": name,
        "description": f"{SOURCE_NOTE}, database {db_id}: {summary_en} ({count}). English questions with evidence.",
        "listed": False,
    }
    write(os.path.join(folder, "dataset.json"), json.dumps(config, ensure_ascii=False, indent=2) + "\n")

    cases, seen = [], {}
    for q in questions:
        case = {
            "id": q["question_id"],
            "question": q["question"],
            "evidence": q["evidence"],
            "category": "bird",
            "difficulty": q["difficulty"],
            "ground_truth_sql": q["SQL"],
        }
        if case["id"] in seen:
            if seen[case["id"]] != case:
                raise ValueError(f"{db_id}: question id {case['id']} with two different contents")
            continue
        seen[case["id"]] = case
        cases.append(case)
    return name, cases


def check_ground_truths(name, cases):
    """(kept cases, excluded cases with the reason) as the evaluator would run them."""
    from database import execute_query
    from pipeline import PipelineConfig, open_connection
    from sql_structural_validator import validate_sql_structure
    from sql_tables import tables_in_sql
    from evaluation.comparison import is_order_sensitive

    kept, excluded = [], []
    conn = open_connection(PipelineConfig(dataset=name))
    try:
        for case in cases:
            sql = case["ground_truth_sql"]
            reason = None
            is_valid, error = validate_sql_structure(sql)
            if not is_valid:
                reason = f"structural validation: {error}"
            else:
                try:
                    is_order_sensitive(sql)
                    tables_in_sql(sql)
                except Exception as e:
                    reason = f"sqlglot cannot parse it: {e}"
            if reason is None:
                start = time.perf_counter()
                try:
                    execute_query(conn, sql)
                except Exception as e:
                    reason = f"execution ({time.perf_counter() - start:.1f} s): {str(e).strip()}"
            if reason is None:
                kept.append(case)
            else:
                excluded.append({**case, "reason": reason})
    finally:
        conn.close()
    return kept, excluded


def main():
    parser = argparse.ArgumentParser(description="BIRD Mini-Dev importálása (PostgreSQL-változat)")
    parser.add_argument("minidev", help="a kicsomagolt minidev.zip mappája")
    parser.add_argument("--reload", action="store_true", help="a staging adatbázis újratöltése")
    parser.add_argument("--keep-staging", action="store_true", help="a staging adatbázis megtartása")
    args = parser.parse_args()

    source = os.path.join(args.minidev, "MINIDEV")
    dump_path = os.path.join(args.minidev, "MINIDEV_postgresql", "BIRD_dev.sql")
    with open(os.path.join(source, "dev_tables.json"), encoding="utf-8") as file:
        table_lists = {d["db_id"]: [t.lower() for t in d["table_names_original"]] for d in json.load(file)}
    with open(os.path.join(source, "mini_dev_postgresql.json"), encoding="utf-8") as file:
        questions = json.load(file)
    by_db = defaultdict(list)
    for q in questions:
        by_db[q["db_id"]].append(q)

    print("Reading the dump...")
    dump = parse_dump(dump_path)
    load_staging(dump_path, args.reload)

    report = {}
    for db_id in sorted(by_db):
        print(f"\n== {db_id}")
        name, cases = write_dataset(db_id, table_lists[db_id], dump, by_db[db_id])
        subprocess.run(
            [sys.executable, os.path.join(DATABASE_DIR, "setup_dataset.py"), name, "--recreate"],
            check=True,
        )
        kept, excluded = check_ground_truths(name, cases)
        folder = os.path.join(DATASETS_DIR, name)
        write(os.path.join(folder, "test_cases", "en.json"), json.dumps(kept, ensure_ascii=False, indent=2) + "\n")
        write(os.path.join(folder, "excluded_cases.json"), json.dumps(excluded, ensure_ascii=False, indent=2) + "\n")
        report[db_id] = (len(by_db[db_id]), len(cases), len(kept))
        for case in excluded:
            print(f"  excluded #{case['id']}: {case['reason'][:150]}")

    if not args.keep_staging:
        psql("postgres", f"DROP DATABASE {STAGING_DB};")

    print("\nDatabase: questions in BIRD / distinct / kept")
    for db_id, (total, distinct, kept) in report.items():
        print(f"  {db_id:<25} {total:>3} / {distinct:>3} / {kept:>3}")
    print(f"  {'total':<25} {sum(r[0] for r in report.values()):>3} / "
          f"{sum(r[1] for r in report.values()):>3} / {sum(r[2] for r in report.values()):>3}")


if __name__ == "__main__":
    main()
