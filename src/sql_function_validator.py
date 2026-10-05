"""
Offline blocklist of dangerous PostgreSQL functions.

The structural validator checks that a query is a single read-only
SELECT, but a SELECT may still call functions that do more than read
data: pause the connection, cancel other sessions, change settings,
take locks that outlive the transaction, run SQL given as a string,
or touch the server's files.

The read-only database role is the real security boundary -- it denies
the file and catalog functions outright. This blocklist is an earlier,
cheaper layer that rejects such calls before PostgreSQL runs them, with
a clear reason, and also covers behaviour the role still allows
(pg_sleep, set_config, advisory locks).

It is a blocklist by design: a function not on the list is allowed, so
a new PostgreSQL version or extension can introduce one this list does
not know. Matching is by name only. It therefore reduces risk; it does
not remove it, which is why the role, not this check, is the boundary.
"""

import sqlglot
from sqlglot import exp


# Lower-case function names, grouped by why each group is blocked.
# The groups are the explanation, not only the list.
BLOCKED_FUNCTIONS = frozenset({
    # Tie up a connection (denial of service). The statement timeout
    # stops a single call, but not many issued in parallel.
    "pg_sleep", "pg_sleep_for", "pg_sleep_until",
    # Reach into other database sessions.
    "pg_terminate_backend", "pg_cancel_backend",
    # Change session settings from inside a query.
    "set_config",
    # Locks a transaction rollback does NOT release, so they would
    # leak from one question into the next.
    "pg_advisory_lock", "pg_advisory_lock_shared",
    "pg_try_advisory_lock", "pg_try_advisory_lock_shared",
    # Run SQL passed as a string -- a way around this very check.
    "query_to_xml", "query_to_xmlschema", "query_to_xml_and_xmlschema",
    "dblink", "dblink_exec",
    # Read or write files on the server.
    "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "pg_stat_file",
    "lo_import", "lo_export", "lo_get", "lo_put",
    # Advance or set a sequence -- a write hidden inside a SELECT.
    "nextval", "setval",
})


def validate_sql_functions(sql: str, blocked=BLOCKED_FUNCTIONS) -> tuple[bool, str]:
    """
    Reject a query that calls a blocked function.

    Meant to run after validate_sql_structure, so the SQL is already
    known to parse as a single SELECT. Matching is case-insensitive;
    a schema-qualified call (pg_catalog.pg_sleep) keeps the same name
    and is caught too.
    """
    try:
        tree = sqlglot.parse_one(sql, read="postgres")
    except sqlglot.errors.ParseError as e:
        return False, f"SQL syntax error: {e}"

    # Dangerous functions are not built into sqlglot's grammar, so they
    # parse as Anonymous nodes whose name is the function name.
    for func in tree.find_all(exp.Anonymous):
        name = func.name.lower()
        if name in blocked:
            return False, f"Forbidden function: {name}"

    return True, ""
