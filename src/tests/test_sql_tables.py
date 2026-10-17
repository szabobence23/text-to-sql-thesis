import pytest

from sql_tables import format_tables, table_recall, tables_in_sql


@pytest.mark.parametrize(
    "sql, expected",
    [
        ("SELECT COUNT(*) FROM orders", {("public", "orders")}),
        # Joins, aliases and upper case.
        (
            "SELECT c.customer_state FROM Orders o JOIN customers c ON o.customer_id = c.customer_id",
            {("public", "orders"), ("public", "customers")},
        ),
        # Schema-qualified tables keep their schema.
        (
            "SELECT * FROM sales.customer c JOIN person.person p ON c.personid = p.businessentityid",
            {("sales", "customer"), ("person", "person")},
        ),
        # A table only used in a subquery is still needed.
        (
            "SELECT r.name FROM races r WHERE r.round = (SELECT MAX(round) FROM races WHERE year = 2007)",
            {("public", "races")},
        ),
        # A CTE name is not a table; the tables inside it are.
        (
            "WITH t AS (SELECT order_id FROM order_items) SELECT COUNT(*) FROM t",
            {("public", "order_items")},
        ),
    ],
)
def test_tables_in_sql(sql, expected):
    assert tables_in_sql(sql) == expected


def test_table_recall():
    gold = {("public", "a"), ("public", "b")}

    assert table_recall(gold, gold | {("public", "c")}) == 1.0
    assert table_recall(gold, {("public", "a")}) == 0.5
    assert table_recall(set(), set()) == 1.0


def test_format_tables_matches_schema_text_names():
    assert format_tables({("sales", "customer"), ("public", "orders")}) == [
        "orders", "sales.customer"
    ]
