import pytest

from database import get_connection
from pipeline import PipelineConfig, load_schema
from schema import SCHEMA_HINTS


@pytest.fixture
def conn():
    connection = get_connection()

    try:
        yield connection
    finally:
        connection.close()


def test_default_config_is_serializable():
    config = PipelineConfig().to_dict()

    assert config["schema_hints"] is True
    assert config["llm"]["temperature"] == 0.0


@pytest.mark.db
def test_schema_hints_switch(conn):
    with_hints = load_schema(conn, PipelineConfig(schema_hints=True))
    without_hints = load_schema(conn, PipelineConfig(schema_hints=False))

    assert SCHEMA_HINTS in with_hints
    assert SCHEMA_HINTS not in without_hints
    # FK relationships must survive the read-only role (pg_catalog query).
    assert "- orders.customer_id -> customers.customer_id" in without_hints
