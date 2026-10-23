from schema import _quote, qualified_name


def test_values_are_quoted_as_sql_literals():
    assert _quote("canceled") == "'canceled'"
    assert _quote("D'Hers") == "'D''Hers'"


def test_public_tables_keep_bare_names():
    assert qualified_name("public", "orders") == "orders"
    assert qualified_name("sales", "customer") == "sales.customer"
