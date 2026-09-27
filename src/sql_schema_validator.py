import uuid

import psycopg


def validate_sql_schema(conn, sql: str) -> tuple[bool, str]:
    """
    Validate a SELECT query against the actual PostgreSQL schema.

    Checks table names, column names, aliases, JOIN references,
    and PostgreSQL type compatibility during query preparation.

    Does not fetch query results.
    """

    if not sql or not sql.strip():
        return False, "Empty SQL query."

    # Generate a unique identifier for the prepared statement.
    statement_name = f"schema_check_{uuid.uuid4().hex}"

    # SQL is interpolated into PREPARE, so this must only run after
    # validate_sql_structure has accepted it as a single SELECT.
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"PREPARE {statement_name} AS {sql}"
            )

            cur.execute(
                f"DEALLOCATE {statement_name}"
            )

        return True, ""

    except psycopg.Error as e:
        return False, str(e).strip()

    finally:
        conn.rollback()