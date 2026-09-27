import pytest

from llm import extract_sql


@pytest.mark.parametrize(
    "response",
    [
        "SELECT 1;",
        "```sql\nSELECT 1;\n```",
        "```postgresql\nSELECT 1;\n```",
        "```\nSELECT 1;\n```",
        "Here is the query:\n```sql\nSELECT 1;\n```\nIt counts rows.",
    ],
)
def test_extract_sql(response):
    assert extract_sql(response) == "SELECT 1;"
