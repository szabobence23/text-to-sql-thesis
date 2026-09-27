import os

import psycopg


# Defaults point at the local docker-compose server and the
# read-only role from database/readonly_role.sql. Generated SQL
# must never run as a superuser. The database name comes from the
# dataset (dataset_loader), not from here.
DB_HOST = os.getenv("TEXT2SQL_DB_HOST", "localhost")
DB_PORT = int(os.getenv("TEXT2SQL_DB_PORT", "5432"))
DB_USER = os.getenv("TEXT2SQL_DB_USER", "text2sql_reader")
DB_PASSWORD = os.getenv("TEXT2SQL_DB_PASSWORD", "text2sql_reader")
STATEMENT_TIMEOUT_MS = int(os.getenv("TEXT2SQL_STATEMENT_TIMEOUT_MS", "10000"))


def get_connection(db_name):
    # Read-only mode and timeout are also set on the role itself;
    # repeating them here keeps them in force for any other user.
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=db_name,
        user=DB_USER,
        password=DB_PASSWORD,
        options=(
            f"-c statement_timeout={STATEMENT_TIMEOUT_MS} "
            "-c default_transaction_read_only=on"
        ),
    )


def execute_query(conn, sql):
    """
    Run a query and return its rows.

    The transaction is always rolled back, so nothing a query does
    to the session (e.g. set_config) can leak into the next query.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()
    finally:
        conn.rollback()
