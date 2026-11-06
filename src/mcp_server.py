"""
MCP server: the text-to-SQL system as tools for an MCP client.

    python src/mcp_server.py

Another front-end of pipeline.run_pipeline, over the same engines as the
web UI (service.py, pipeline.app_config). The client (Claude Desktop,
Claude Code, ...) starts it as a subprocess and talks JSON-RPC over
stdin/stdout (stdio transport); the SDK diverts stray prints to stderr.

Two ways to use it: ask_database runs the whole system (the local model
writes the SQL); the raw tools (get_schema, find_tables, find_examples,
run_sql) let the client's own model write the SQL, with run_sql going
through the same validators and read-only role as the pipeline's queries.

Tool texts are in English: they are read by the client's model, not by
the user. Rows returned here leave the machine if the client's model runs
in the cloud, so at most MAX_ROWS of them are sent by default.
"""

from contextlib import contextmanager
from typing import Annotated, Literal

import psycopg
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import BaseModel, Field

import service
from dataset_loader import available_datasets, load_dataset
from service import jsonable
from sql_tables import format_tables


MAX_ROWS = 50
MAX_ROWS_LIMIT = 200

INSTRUCTIONS = """\
Text-to-SQL over local PostgreSQL databases. Call list_databases first to
pick the database. Two ways to answer a question:

1. ask_database: the local text-to-SQL system (qwen2.5-coder:7b) writes and
   runs a read-only query and answers in the question's language. When
   `doubtful` is true, its own check found the rows suspicious: tell the user.
2. Write the SQL yourself: get_schema (or find_tables, then get_schema with
   those tables on large databases), find_examples for solved questions of
   the same database, then run_sql. run_sql only runs a single read-only
   PostgreSQL SELECT; other statements and some functions are rejected.

Questions may be in any language; most test questions are Hungarian."""

DatabaseName = Literal[*available_datasets()]
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)

Question = Annotated[str, Field(min_length=1, max_length=2000, description="The question, in natural language")]
Database = Annotated[DatabaseName, Field(description="Database name from list_databases")]


class DatabaseInfo(BaseModel):
    name: str
    label: str
    summary: str
    description: str


class AskResult(BaseModel):
    database: str
    question: str
    answer: str | None = Field(description="Answer written by the local model from the rows, in the question's language")
    doubtful: bool | None = Field(description="True: the local model's check found the result suspicious")
    sql: str = Field(description="The final SQL query (the one that ran, or the last failed attempt)")
    error: str | None = Field(description="Why no working query was found; None when the query ran")
    columns: list[str]
    rows: list[list]
    row_count: int = Field(description=f"Number of rows the query returned (rows holds at most the first {MAX_ROWS})")
    tables: list[str] | None = Field(description="Tables shown to the model; None = the whole schema")
    correction_rounds: int
    seconds: float


class TableMatch(BaseModel):
    name: str
    columns: list[str]
    score: float = Field(description="Similarity of the table to the question (higher is closer)")
    bridge: bool = Field(description="Not among the top k: joins two of them by foreign keys")


class ExampleMatch(BaseModel):
    id: int
    question: str
    sql: str
    score: float = Field(description="Similarity to the question (cosine, 1 = same meaning)")


class SqlResult(BaseModel):
    columns: list[str]
    rows: list[list]
    truncated: bool = Field(description="The query returned more rows than max_rows")


@contextmanager
def tool_errors():
    """Failures as ToolError, so the client's model reads the reason."""
    try:
        yield
    except ToolError:
        raise
    except psycopg.OperationalError as error:
        raise ToolError(f"Cannot reach the database (is the Docker container running?): {error}")
    except ValueError as error:  # bad input, e.g. an unknown table name
        raise ToolError(str(error))
    except Exception as error:
        raise ToolError(f"The text-to-SQL system failed (is Ollama running?): {error}")


# WARNING: the default INFO logs every Ollama HTTP request to stderr.
mcp = MCPServer(name="text-to-sql", instructions=INSTRUCTIONS, log_level="WARNING")


@mcp.tool(annotations=READ_ONLY)
def list_databases() -> list[DatabaseInfo]:
    """List the databases the other tools can query, with what each one holds."""
    infos = []
    for name in available_datasets():
        dataset = load_dataset(name)
        infos.append(DatabaseInfo(
            name=name,
            label=dataset.label("en"),
            summary=dataset.summary("en"),
            description=dataset.description,
        ))
    return infos


@mcp.tool(annotations=READ_ONLY)
def ask_database(question: Question, database: Database) -> AskResult:
    """Answer a question about one database: the local text-to-SQL system writes a
    read-only PostgreSQL query (with corrections when it fails), runs it and
    answers from the rows. Takes about 10-60 seconds."""
    question = question.strip()
    with tool_errors():
        engine, result, seconds = service.ask(database, question)

    rows = result.rows or []
    return AskResult(
        database=database,
        question=question,
        answer=result.answer.text if result.answer else None,
        doubtful=result.answer.doubtful if result.answer else None,
        sql=result.sql,
        error=result.validation_error or result.execution_error or None,
        columns=result.columns or [],
        rows=[[jsonable(v) for v in row] for row in rows[:MAX_ROWS]],
        row_count=len(rows),
        tables=format_tables(result.schema_tables) if result.schema_tables is not None else None,
        correction_rounds=result.correction_rounds,
        seconds=round(seconds, 1),
    )


@mcp.tool(annotations=READ_ONLY)
def get_schema(
    database: Database,
    tables: Annotated[
        list[str] | None,
        Field(description="Only these tables (names as find_tables or the full schema shows them); default: all"),
    ] = None,
) -> str:
    """The database schema as the local model sees it: tables, columns with types,
    foreign-key relationships and notes on the data. On large databases
    (adventureworks: 68 tables) pass the tables found by find_tables."""
    with tool_errors():
        return service.schema_text(database, tables)


@mcp.tool(annotations=READ_ONLY)
def find_tables(
    question: Question,
    database: Database,
    k: Annotated[int, Field(ge=1, le=30, description="Number of best-matching tables")] = 10,
) -> list[TableMatch]:
    """The tables most likely needed for a question (multilingual embedding search,
    as in the local system), best first, plus the tables that join them."""
    with tool_errors():
        matches = service.find_tables(database, question, k)
    return [
        TableMatch(name=m.name, columns=list(m.columns), score=round(m.score, 4), bridge=m.bridge)
        for m in matches
    ]


@mcp.tool(annotations=READ_ONLY)
def find_examples(
    question: Question,
    database: Database,
    n: Annotated[int, Field(ge=1, le=10, description="Number of examples")] = 3,
) -> list[ExampleMatch]:
    """Solved questions of the database with correct SQL, most similar first; they
    show the database's conventions. Empty when the database has none."""
    with tool_errors():
        matches = service.find_examples(database, question, n)
    return [
        ExampleMatch(id=m.example.id, question=m.question, sql=m.example.sql, score=round(m.score, 4))
        for m in matches
    ]


@mcp.tool(annotations=READ_ONLY)
def run_sql(
    sql: Annotated[str, Field(min_length=1, max_length=20000, description="One PostgreSQL SELECT query")],
    database: Database,
    max_rows: Annotated[int, Field(ge=1, le=MAX_ROWS_LIMIT, description="Rows to return at most")] = MAX_ROWS,
) -> SqlResult:
    """Run one read-only query. It is validated first (single SELECT, no blocked
    functions, names and types checked by PostgreSQL) and runs as a read-only
    database role with a 10-second timeout; the error says which check failed."""
    with tool_errors():
        run = service.run_sql(database, sql, max_rows)
    if run.error:
        raise ToolError(run.error)
    return SqlResult(
        columns=run.columns,
        rows=[[jsonable(v) for v in row] for row in run.rows],
        truncated=run.truncated,
    )


if __name__ == "__main__":
    mcp.run()
