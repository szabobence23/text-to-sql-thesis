import time
from dataclasses import asdict, dataclass, field

import psycopg

from database import execute_query
from llm import LLMSettings, generate_sql
from schema import get_schema
from sql_validator import validate_sql


@dataclass(frozen=True)
class PipelineConfig:
    """
    Which pipeline features run, and with what parameters.

    Defaults reproduce the baseline. Every new feature gets a switch
    here (off by default), so it can be measured with and without it
    and the evaluator records exactly what was enabled.
    """
    llm: LLMSettings = field(default_factory=LLMSettings)
    # Hand-written dataset notes appended to the schema text.
    schema_hints: bool = True

    def to_dict(self):
        return asdict(self)


def load_schema(conn, config: PipelineConfig) -> str:
    # Schema text depends on the config, so it is built here rather
    # than by callers, which could pass a mismatching setting.
    return get_schema(conn, include_hints=config.schema_hints)


@dataclass
class PipelineResult:
    question: str
    sql: str
    raw_response: str
    is_valid: bool
    validation_error: str
    executed: bool
    rows: list | None
    execution_error: str
    prompt_tokens: int
    completion_tokens: int
    timings: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def run_pipeline(conn, question, schema, config: PipelineConfig) -> PipelineResult:
    """
    Question -> SQL generation -> validation -> execution.

    Shared by main.py and the evaluator, so what is measured is
    exactly what runs. Invalid SQL is never executed.
    schema must come from load_schema with the same config.
    """
    timings = {}

    start = time.perf_counter()
    generation = generate_sql(question, schema, config.llm)
    timings["generation_s"] = time.perf_counter() - start

    start = time.perf_counter()
    is_valid, validation_error = validate_sql(conn, generation.sql)
    timings["validation_s"] = time.perf_counter() - start

    rows = None
    executed = False
    execution_error = ""

    if is_valid:
        start = time.perf_counter()
        try:
            rows = execute_query(conn, generation.sql)
            executed = True
        except psycopg.Error as e:
            execution_error = str(e).strip()
        timings["execution_s"] = time.perf_counter() - start

    return PipelineResult(
        question=question,
        sql=generation.sql,
        raw_response=generation.raw_response,
        is_valid=is_valid,
        validation_error=validation_error,
        executed=executed,
        rows=rows,
        execution_error=execution_error,
        prompt_tokens=generation.prompt_tokens,
        completion_tokens=generation.completion_tokens,
        timings=timings,
    )
