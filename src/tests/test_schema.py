from schema import _quote, qualified_name, sql_identifier


def test_values_are_quoted_as_sql_literals():
    assert _quote("canceled") == "'canceled'"
    assert _quote("D'Hers") == "'D''Hers'"


def test_public_tables_keep_bare_names():
    assert qualified_name("public", "orders") == "orders"
    assert qualified_name("sales", "customer") == "sales.customer"


def test_only_names_that_need_it_are_double_quoted():
    assert sql_identifier("order_status") == "order_status"
    assert sql_identifier("Free Meal Count (K-12)") == '"Free Meal Count (K-12)"'
    assert sql_identifier("CustomerID") == '"CustomerID"'
    assert sql_identifier('a"b') == '"a""b"'
