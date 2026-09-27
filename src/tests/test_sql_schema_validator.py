
import pytest

from database import get_connection
from dataset_loader import load_dataset
from sql_schema_validator import validate_sql_schema
from sql_validator import validate_sql


pytestmark = pytest.mark.db


@pytest.fixture
def conn():
    connection = get_connection(load_dataset("olist").db_name)

    try:
        yield connection
    finally:
        connection.close()


@pytest.mark.parametrize(
    "sql, expected_valid",
    [
        # 1. Existing table and column
        (
            "SELECT order_id FROM orders;",
            True,
        ),

        # 2. Existing aggregation
        (
            "SELECT AVG(price) FROM order_items;",
            True,
        ),

        # 3. Valid JOIN
        (
            """
            SELECT p.product_id, SUM(oi.price)
            FROM order_items oi
            JOIN products p
                ON oi.product_id = p.product_id
            GROUP BY p.product_id;
            """,
            True,
        ),

        # 4. Valid CTE
        (
            """
            WITH order_counts AS (
                SELECT customer_id, COUNT(*) AS total
                FROM orders
                GROUP BY customer_id
            )
            SELECT *
            FROM order_counts;
            """,
            True,
        ),

        # 5. Valid category translation JOIN
        (
            """
            SELECT pt.product_category_name_english
            FROM products p
            LEFT JOIN product_category_name_translation pt
                ON p.product_category_name =
                   pt.product_category_name
            LIMIT 5;
            """,
            True,
        ),

        # 6. Nonexistent column
        (
            "SELECT products.price FROM products;",
            False,
        ),

        # 7. Nonexistent table
        (
            "SELECT * FROM nonexistent_table;",
            False,
        ),

        # 8. Wrong alias
        (
            """
            SELECT pt.product_category_name_english
            FROM products p
            LIMIT 5;
            """,
            False,
        ),

        # 9. Ambiguous column
        (
            """
            SELECT customer_id
            FROM orders o
            JOIN customers c
                ON o.customer_id = c.customer_id;
            """,
            False,
        ),

        # 10. Wrong column in WHERE
        (
            """
            SELECT *
            FROM products
            WHERE price > 100;
            """,
            False,
        ),

        # 11. Wrong GROUP BY reference
        (
            """
            SELECT customer_state, COUNT(*)
            FROM customers
            GROUP BY nonexistent_column;
            """,
            False,
        ),

        # 12. Wrong JOIN reference
        (
            """
            SELECT *
            FROM orders o
            JOIN products p
                ON o.product_id = p.product_id;
            """,
            False,
        ),
    ],
)
def test_sql_schema_validation(conn, sql, expected_valid):
    is_valid, error_message = validate_sql_schema(conn, sql)

    assert is_valid == expected_valid, (
        f"\nSQL:\n{sql}\n"
        f"Expected valid: {expected_valid}\n"
        f"Actual valid: {is_valid}\n"
        f"Error: {error_message}"
    )


@pytest.mark.parametrize(
    "sql, expected_stage",
    [
        ("SELECT COUNT(*) FROM orders;", None),
        ("DELETE FROM orders;", "Structural"),
        ("SELECT products.price FROM products;", "Schema"),
    ],
)
def test_validate_sql_runs_both_stages(conn, sql, expected_stage):
    is_valid, error_message = validate_sql(conn, sql)

    if expected_stage is None:
        assert is_valid, error_message
    else:
        assert not is_valid
        assert error_message.startswith(expected_stage), error_message
