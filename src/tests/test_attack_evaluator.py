from types import SimpleNamespace

import pytest

from evaluation.attack_evaluator import layer_of_tool_result
from sql_validator import validate_sql


def tool_result(text=None):
    if text is None:
        return SimpleNamespace(is_error=False, content=[])
    return SimpleNamespace(is_error=True, content=[SimpleNamespace(text=f"Error executing tool run_sql: {text}")])


@pytest.mark.parametrize("sql, layer", [
    ("DELETE FROM orders", "structure"),
    ("SELECT pg_sleep(30)", "function"),
])
def test_layer_of_real_validator_errors(sql, layer):
    # The offline stages return before touching the connection.
    is_valid, error = validate_sql(None, sql)
    assert not is_valid

    assert layer_of_tool_result(tool_result(error))[0] == layer


def test_layer_of_tool_result():
    assert layer_of_tool_result(tool_result()) == ("none", "")
    assert layer_of_tool_result(tool_result('Schema validation failed: column "x" does not exist')) == (
        "schema", 'column "x" does not exist',
    )
    assert layer_of_tool_result(tool_result("Execution failed: permission denied for table pg_authid")) == (
        "database", "permission denied for table pg_authid",
    )
    with pytest.raises(RuntimeError, match="Unexpected"):
        layer_of_tool_result(tool_result("The text-to-SQL system failed (is Ollama running?)"))
