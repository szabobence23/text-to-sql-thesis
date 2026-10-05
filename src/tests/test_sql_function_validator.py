import pytest

from sql_function_validator import validate_sql_functions


@pytest.mark.parametrize(
    "sql",
    [
        # Plain analytical queries: no blocked function.
        "SELECT count(*) FROM orders",
        "SELECT avg(price), sum(price) FROM order_items",
        "SELECT date_trunc('month', order_purchase_timestamp) FROM orders",
        "SELECT extract(year FROM order_purchase_timestamp) FROM orders",
        "SELECT coalesce(c.name, 'n/a') FROM customers c",
        # A column that merely contains a blocked name is not a call.
        "SELECT nextval FROM my_table",
    ],
)
def test_allows_safe_queries(sql):
    is_valid, error = validate_sql_functions(sql)
    assert is_valid, error


@pytest.mark.parametrize(
    "sql, name",
    [
        ("SELECT pg_sleep(10)", "pg_sleep"),
        ("SELECT pg_terminate_backend(1)", "pg_terminate_backend"),
        ("SELECT set_config('statement_timeout', '0', false)", "set_config"),
        ("SELECT pg_advisory_lock(1)", "pg_advisory_lock"),
        ("SELECT query_to_xml('SELECT 1', true, true, '')", "query_to_xml"),
        ("SELECT lo_import('/etc/passwd')", "lo_import"),
        ("SELECT pg_read_file('/etc/passwd')", "pg_read_file"),
        ("SELECT nextval('seq')", "nextval"),
        # Buried in a WHERE clause, not just the select list.
        ("SELECT count(*) FROM orders WHERE pg_sleep(10) IS NULL", "pg_sleep"),
        # Schema-qualified: same function name.
        ("SELECT pg_catalog.pg_sleep(10)", "pg_sleep"),
        # Case does not matter.
        ("SELECT PG_SLEEP(10)", "pg_sleep"),
    ],
)
def test_blocks_dangerous_functions(sql, name):
    is_valid, error = validate_sql_functions(sql)
    assert not is_valid
    assert name in error


def test_blocklist_can_be_overridden():
    # An empty blocklist allows everything (used to measure its effect).
    is_valid, _ = validate_sql_functions("SELECT pg_sleep(10)", blocked=frozenset())
    assert is_valid
