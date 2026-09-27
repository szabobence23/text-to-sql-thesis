
import pytest

from sql_structural_validator import validate_sql_structure


@pytest.mark.parametrize(
    "sql, expected_valid",
    [
        # 1. Basic SELECT
        (
            "SELECT * FROM orders;",
            True,
        ),

        # 2. WHERE + aggregation
        (
            "SELECT COUNT(*) FROM orders "
            "WHERE order_status = 'canceled';",
            True,
        ),

        # 3. JOIN + GROUP BY
        (
            """
            SELECT p.product_id, SUM(oi.price) AS revenue
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            GROUP BY p.product_id
            ORDER BY revenue DESC
            LIMIT 5;
            """,
            True,
        ),

        # 4. CTE
        (
            """
            WITH order_counts AS (
                SELECT customer_id, COUNT(*) AS total
                FROM orders
                GROUP BY customer_id
            )
            SELECT *
            FROM order_counts
            WHERE total > 1;
            """,
            True,
        ),

        # 5. Subquery
        (
            """
            SELECT customer_id
            FROM orders
            WHERE customer_id IN (
                SELECT customer_id
                FROM orders
                GROUP BY customer_id
                HAVING COUNT(*) > 1
            );
            """,
            True,
        ),

        # 6. ORDER BY + LIMIT
        (
            "SELECT product_id FROM products "
            "ORDER BY product_id LIMIT 5;",
            True,
        ),

        # 7. Empty SQL
        (
            "",
            False,
        ),

        # 8. Invalid syntax
        (
            "SELECT FROM WHERE;",
            False,
        ),

        # 9. DROP
        (
            "DROP TABLE orders;",
            False,
        ),

        # 10. DELETE
        (
            "DELETE FROM orders;",
            False,
        ),

        # 11. UPDATE
        (
            "UPDATE orders SET order_status = 'canceled';",
            False,
        ),

        # 12. INSERT
        (
            "INSERT INTO orders (order_id) VALUES ('123');",
            False,
        ),

        # 13. CREATE
        (
            "CREATE TABLE test_table (id INT);",
            False,
        ),

        # 14. Multiple statements
        (
            "SELECT * FROM orders; DROP TABLE orders;",
            False,
        ),

        # 15. SELECT INTO
        (
            "SELECT * INTO new_table FROM orders;",
            False,
        ),

        # 16. FOR UPDATE
        (
            "SELECT * FROM orders FOR UPDATE;",
            False,
        ),

        # 17. Multiline SELECT
        (
            """
            SELECT
                customer_state,
                COUNT(*) AS total
            FROM customers
            GROUP BY customer_state;
            """,
            True,
        ),

        # 18. SQL comment
        (
            """
            -- Count all orders
            SELECT COUNT(*) FROM orders;
            """,
            True,
        ),

        # 19. DELETE hidden inside a CTE
        (
            """
            WITH deleted AS (
                DELETE FROM orders
                RETURNING *
            )
            SELECT * FROM deleted;
            """,
            False,
        ),

        # 20. SELECT followed by another statement
        (
            "SELECT * FROM orders; SELECT * FROM customers;",
            False,
        ),
    ],
)
def test_validate_sql_structure(sql, expected_valid):
    is_valid, error_message = validate_sql_structure(sql)

    assert is_valid == expected_valid, (
        f"Unexpected validation result for SQL:\n{sql}\n"
        f"Expected valid: {expected_valid}\n"
        f"Actual valid: {is_valid}\n"
        f"Error: {error_message}"
    )