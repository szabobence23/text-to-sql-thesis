"""
Create a dataset's database in the docker-compose PostgreSQL container:
database -> schema.sql -> import.sql -> read-only role grants.

    python database/setup_dataset.py olist
    python database/setup_dataset.py sales --recreate

Runs psql inside the container as the postgres superuser. import.sql
reads its files from /datasets/<name>/data (datasets/ is mounted there).
"""

import argparse
import os
import re
import subprocess
import sys

DATABASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(DATABASE_DIR), "src"))

from dataset_loader import available_datasets, load_dataset


CONTAINER = os.getenv("TEXT2SQL_PG_CONTAINER", "text-to-sql-postgres")
READONLY_ROLE_SQL = os.path.join(DATABASE_DIR, "readonly_role.sql")


def psql(db, sql, variables=None, capture=False):
    command = [
        "docker", "exec", "-i", CONTAINER,
        "psql", "-U", "postgres", "-d", db,
        "-v", "ON_ERROR_STOP=1", "-q",
    ]
    for key, value in (variables or {}).items():
        command += ["-v", f"{key}={value}"]
    if capture:
        command += ["-tA"]

    result = subprocess.run(
        command,
        input=sql,
        text=True,
        encoding="utf-8",
        capture_output=capture,
    )

    if result.returncode != 0:
        detail = result.stderr if capture else ""
        sys.exit(f"psql failed on {db}. {detail}")

    return result.stdout.strip() if capture else None


def read(path):
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def main():
    parser = argparse.ArgumentParser(description="Dataset adatbázis létrehozása")
    parser.add_argument("dataset", choices=available_datasets())
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="létező adatbázis törlése és újraépítése",
    )
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    db = dataset.db_name

    # Names are interpolated into CREATE/DROP DATABASE and GRANT.
    for name in (db, *dataset.schemas):
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", name):
            sys.exit(f"Invalid name '{name}': use lowercase letters, digits, _")

    mounted = subprocess.run(
        ["docker", "exec", CONTAINER, "test", "-d", f"/datasets/{dataset.name}"]
    )
    if mounted.returncode != 0:
        sys.exit(
            f"/datasets/{dataset.name} is not visible in {CONTAINER}. "
            "Is the container running with the current docker-compose.yml? "
            "(docker compose up -d)"
        )

    exists = psql(
        "postgres",
        f"SELECT 1 FROM pg_database WHERE datname = '{db}';",
        capture=True,
    )

    if exists and not args.recreate:
        sys.exit(f"Database {db} already exists. Use --recreate to rebuild it.")

    if exists:
        print(f"Dropping {db}...")
        psql("postgres", f'DROP DATABASE "{db}" WITH (FORCE);')

    print(f"Creating {db}...")
    psql("postgres", f'CREATE DATABASE "{db}";')

    print("Loading schema...")
    psql(db, read(dataset.schema_sql_path))

    print("Importing data...")
    psql(db, read(dataset.import_sql_path))

    print("Granting read-only access...")
    psql(db, read(READONLY_ROLE_SQL), variables={"db_name": db})

    # readonly_role.sql covers public; datasets with tables in other
    # schemas need read access there too.
    other_schemas = [s for s in dataset.schemas if s != "public"]
    if other_schemas:
        psql(db, "".join(
            f"GRANT USAGE ON SCHEMA {s} TO text2sql_reader;\n"
            f"GRANT SELECT ON ALL TABLES IN SCHEMA {s} TO text2sql_reader;\n"
            for s in other_schemas
        ))

    print(f"Dataset '{dataset.name}' is ready in {db}.")


if __name__ == "__main__":
    main()
