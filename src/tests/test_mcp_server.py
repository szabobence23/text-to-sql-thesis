import datetime
import os
import sys
from decimal import Decimal
from types import SimpleNamespace

import anyio
import psycopg
import pytest
from mcp import Client, StdioServerParameters

import mcp_server
import service
from dataset_loader import available_datasets


SERVER_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_server.py")


def call(name, arguments=None, server=mcp_server.mcp):
    async def run():
        async with Client(server) as client:
            return await client.call_tool(name, arguments or {})
    return anyio.run(run)


def fake_result(executed=True, rows=None, error=""):
    return SimpleNamespace(
        sql="SELECT order_id, price FROM order_items;",
        validation_error="",
        execution_error=error,
        executed=executed,
        columns=["order_id", "price"] if executed else None,
        rows=rows if executed else None,
        schema_tables=[("public", "order_items")],
        correction_rounds=0 if executed else 2,
        answer=SimpleNamespace(text="Ennyi rendelés van.", doubtful=False) if executed else None,
    )


@pytest.fixture
def fake_ask(monkeypatch):
    asked = []

    def install(result=None, error=None):
        def ask(dataset, question):
            asked.append((dataset, question))
            if error:
                raise error
            return SimpleNamespace(), result, 12.345
        monkeypatch.setattr(service, "ask", ask)
        return asked

    return install


def test_tools_are_listed_read_only():
    async def run():
        async with Client(mcp_server.mcp) as client:
            return (await client.list_tools()).tools
    tools = {tool.name: tool for tool in anyio.run(run)}

    assert set(tools) == {"list_databases", "ask_database", "get_schema", "find_tables", "find_examples", "run_sql"}
    assert all(tool.annotations.read_only_hint for tool in tools.values())
    database = tools["ask_database"].input_schema["properties"]["database"]
    assert database["enum"] == available_datasets()


def test_list_databases():
    result = call("list_databases")

    assert not result.is_error
    databases = result.structured_content["result"]
    assert [d["name"] for d in databases] == available_datasets()
    olist = next(d for d in databases if d["name"] == "olist")
    assert olist["label"] and olist["summary"] and olist["description"]


def test_ask_database_returns_limited_jsonable_rows(fake_ask):
    rows = [(f"o{i}", Decimal("1.50")) for i in range(mcp_server.MAX_ROWS + 10)]
    rows[0] = ("o0", datetime.date(2018, 1, 2))
    asked = fake_ask(fake_result(rows=rows))

    result = call("ask_database", {"question": "  Mennyi?  ", "database": "olist"})

    assert asked == [("olist", "Mennyi?")]
    assert not result.is_error
    content = result.structured_content
    assert content["answer"] == "Ennyi rendelés van."
    assert content["doubtful"] is False
    assert content["error"] is None
    assert content["columns"] == ["order_id", "price"]
    assert len(content["rows"]) == mcp_server.MAX_ROWS
    assert content["row_count"] == mcp_server.MAX_ROWS + 10
    assert content["rows"][0] == ["o0", "2018-01-02"]
    assert content["rows"][1] == ["o1", 1.5]
    assert content["tables"] == ["order_items"]
    assert content["seconds"] == 12.3


def test_ask_database_reports_failed_query(fake_ask):
    fake_ask(fake_result(executed=False, error='relation "x" does not exist'))

    content = call("ask_database", {"question": "Mennyi?", "database": "olist"}).structured_content

    assert content["error"] == 'relation "x" does not exist'
    assert content["answer"] is None
    assert content["rows"] == [] and content["row_count"] == 0
    assert content["correction_rounds"] == 2


def test_ask_database_errors_reach_the_client(fake_ask):
    fake_ask(error=psycopg.OperationalError("connection refused"))
    result = call("ask_database", {"question": "Mennyi?", "database": "olist"})
    assert result.is_error
    assert "Docker" in result.content[0].text and "connection refused" in result.content[0].text

    fake_ask(error=ConnectionError("Ollama down"))
    result = call("ask_database", {"question": "Mennyi?", "database": "olist"})
    assert result.is_error and "Ollama down" in result.content[0].text


def test_ask_database_rejects_unknown_database(fake_ask):
    asked = fake_ask(fake_result(rows=[]))

    result = call("ask_database", {"question": "Mennyi?", "database": "nincs_ilyen"})

    assert result.is_error
    assert asked == []


def test_get_schema_passes_tables(monkeypatch):
    asked = []
    monkeypatch.setattr(service, "schema_text", lambda d, t: asked.append((d, t)) or "Table: orders")

    assert call("get_schema", {"database": "olist"}).structured_content == {"result": "Table: orders"}
    call("get_schema", {"database": "olist", "tables": ["orders"]})
    assert asked == [("olist", None), ("olist", ["orders"])]


def test_get_schema_reports_unknown_tables(monkeypatch):
    def schema_text(dataset, tables):
        raise ValueError("Unknown tables: customer (did you mean sales.customer?)")
    monkeypatch.setattr(service, "schema_text", schema_text)

    result = call("get_schema", {"database": "adventureworks", "tables": ["customer"]})

    assert result.is_error
    assert "sales.customer" in result.content[0].text


def test_find_tables_and_examples(monkeypatch):
    monkeypatch.setattr(service, "find_tables", lambda d, q, k: [
        service.TableMatch("orders", ("order_id", "customer_id"), 0.612345, False),
        service.TableMatch("customers", ("customer_id",), 0.4, True),
    ][:k])
    example = SimpleNamespace(id=7, sql="SELECT 1;")
    monkeypatch.setattr(service, "find_examples", lambda d, q, n: [SimpleNamespace(example=example, question="Hány?", score=0.81234)])

    tables = call("find_tables", {"question": "Hány?", "database": "olist", "k": 2}).structured_content["result"]
    examples = call("find_examples", {"question": "Hány?", "database": "olist"}).structured_content["result"]

    assert tables == [
        {"name": "orders", "columns": ["order_id", "customer_id"], "score": 0.6123, "bridge": False},
        {"name": "customers", "columns": ["customer_id"], "score": 0.4, "bridge": True},
    ]
    assert examples == [{"id": 7, "question": "Hány?", "sql": "SELECT 1;", "score": 0.8123}]
    assert call("find_tables", {"question": "Hány?", "database": "olist", "k": 0}).is_error


def test_run_sql(monkeypatch):
    runs = []

    def run_sql(dataset, sql, max_rows):
        runs.append((dataset, sql, max_rows))
        if sql.startswith("DELETE"):
            return service.SqlRun("Structural validation failed: Only SELECT queries are allowed.", [], [], False)
        return service.SqlRun("", ["day", "price"], [(datetime.date(2018, 1, 2), Decimal("2.50"))], True)
    monkeypatch.setattr(service, "run_sql", run_sql)

    content = call("run_sql", {"sql": "SELECT day, price FROM t", "database": "olist"}).structured_content
    assert content == {"columns": ["day", "price"], "rows": [["2018-01-02", 2.5]], "truncated": True}

    result = call("run_sql", {"sql": "DELETE FROM orders", "database": "olist", "max_rows": 5})
    assert result.is_error and "Structural validation failed" in result.content[0].text

    assert runs == [("olist", "SELECT day, price FROM t", mcp_server.MAX_ROWS), ("olist", "DELETE FROM orders", 5)]
    assert call("run_sql", {"sql": "SELECT 1", "database": "olist", "max_rows": mcp_server.MAX_ROWS_LIMIT + 1}).is_error


def test_stdio_server_starts():
    # The real transport: the server as a subprocess, as a client starts it.
    server = StdioServerParameters(command=sys.executable, args=[SERVER_SCRIPT])
    result = call("list_databases", server=server)

    assert not result.is_error
    assert [d["name"] for d in result.structured_content["result"]] == available_datasets()
