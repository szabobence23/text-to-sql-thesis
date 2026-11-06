import threading
from types import SimpleNamespace

import pytest

import service
from pipeline import PipelineConfig, open_connection


def test_resolve_tables():
    engine = SimpleNamespace(tables=[("public", "orders"), ("sales", "customer"), ("sales", "store")])

    assert service.resolve_tables(engine, ["orders", " Sales.Customer "]) == [
        ("public", "orders"), ("sales", "customer"),
    ]
    with pytest.raises(ValueError, match=r"customer \(did you mean sales.customer\?\), nope"):
        service.resolve_tables(engine, ["customer", "nope"])


@pytest.fixture
def olist_engine(monkeypatch):
    # A bare engine: run_sql needs only the connection and the config,
    # so no retriever (and no Ollama) is built.
    config = PipelineConfig(dataset="olist")
    conn = open_connection(config)
    engine = service.Engine(
        config=config, conn=conn, schema="", retriever=None, example_retriever=None,
        tables=[], lock=threading.Lock(),
    )
    monkeypatch.setitem(service._engines, "olist", engine)
    yield engine
    conn.close()


@pytest.mark.db
def test_run_sql_limits_rows(olist_engine):
    run = service.run_sql("olist", "SELECT order_id FROM orders ORDER BY order_id", 3)

    assert run.error == ""
    assert run.columns == ["order_id"]
    assert len(run.rows) == 3 and run.truncated

    run = service.run_sql("olist", "SELECT count(*) FROM orders", 3)
    assert run.rows == [(99441,)] and not run.truncated


@pytest.mark.db
def test_run_sql_rejects_before_executing(olist_engine):
    assert service.run_sql("olist", "DELETE FROM orders", 3).error.startswith("Structural validation failed")
    assert service.run_sql("olist", "SELECT pg_sleep(1)", 3).error.startswith("Function validation failed")
    assert service.run_sql("olist", "SELECT nope FROM orders", 3).error.startswith("Schema validation failed")


@pytest.mark.db
def test_run_sql_reports_database_errors(olist_engine):
    # Passes every validator, refused by the read-only role (attacks.json #23).
    run = service.run_sql("olist", "SELECT * FROM pg_authid", 3)
    assert run.error.startswith("Execution failed") and "permission denied" in run.error

    # The connection stays usable after a failed query.
    assert service.run_sql("olist", "SELECT 1", 3).rows == [(1,)]
