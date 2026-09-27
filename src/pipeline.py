import time
from dataclasses import asdict, dataclass, field

import psycopg

from database import execute_query, get_connection
from dataset_loader import DEFAULT_DATASET, load_dataset
from llm import LLMSettings, correct_sql, generate_sql
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
    # Folder name under datasets/: selects database, hints, test cases.
    dataset: str = DEFAULT_DATASET
    llm: LLMSettings = field(default_factory=LLMSettings)
    # The dataset's hints.txt appended to the schema text.
    schema_hints: bool = True
    # How many times a query that failed validation or execution is sent
    # back to the model with the error. 0 = no correction (baseline).
    max_correction_rounds: int = 0

    def to_dict(self):
        return asdict(self)


def open_connection(config: PipelineConfig):
    return get_connection(load_dataset(config.dataset).db_name)


def load_schema(conn, config: PipelineConfig) -> str:
    # Schema text depends on the config, so it is built here rather
    # than by callers, which could pass a mismatching setting.
    dataset = load_dataset(config.dataset)
    hints = dataset.hints if config.schema_hints else ""
    return get_schema(conn, dataset.db_name, hints)


@dataclass
class Attempt:
    """One generated query and what happened to it."""
    sql: str
    raw_response: str
    is_valid: bool
    validation_error: str
    executed: bool
    execution_error: str
    prompt_tokens: int
    completion_tokens: int
    timings: dict

    @property
    def error(self):
        return self.validation_error or self.execution_error


@dataclass
class PipelineResult:
    """
    The top-level fields describe the final attempt; tokens and
    timings are totals over all attempts (the real cost of an answer).
    """
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
    timings: dict
    attempts: list[Attempt]

    @property
    def correction_rounds(self):
        return len(self.attempts) - 1

    def to_dict(self):
        return asdict(self)


def _run_attempt(conn, generation, generation_s):
    timings = {"generation_s": generation_s}

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

    attempt = Attempt(
        sql=generation.sql,
        raw_response=generation.raw_response,
        is_valid=is_valid,
        validation_error=validation_error,
        executed=executed,
        execution_error=execution_error,
        prompt_tokens=generation.prompt_tokens,
        completion_tokens=generation.completion_tokens,
        timings=timings,
    )

    return attempt, rows


def run_pipeline(conn, question, schema, config: PipelineConfig) -> PipelineResult:
    """
    Question -> SQL generation -> validation -> execution, and when the
    query fails validation or execution, up to max_correction_rounds
    corrections with the error fed back to the model.

    Shared by main.py and the evaluator, so what is measured is
    exactly what runs. Invalid SQL is never executed.
    schema must come from load_schema with the same config.
    """
    attempts = []

    start = time.perf_counter()
    generation = generate_sql(question, schema, config.llm)
    attempt, rows = _run_attempt(conn, generation, time.perf_counter() - start)
    attempts.append(attempt)

    while not attempt.executed and len(attempts) <= config.max_correction_rounds:
        failed = [(a.raw_response, a.error) for a in attempts]

        start = time.perf_counter()
        generation = correct_sql(question, schema, failed, config.llm)
        attempt, rows = _run_attempt(conn, generation, time.perf_counter() - start)
        attempts.append(attempt)

    timings = {}
    for a in attempts:
        for key, seconds in a.timings.items():
            timings[key] = timings.get(key, 0.0) + seconds

    return PipelineResult(
        question=question,
        sql=attempt.sql,
        raw_response=attempt.raw_response,
        is_valid=attempt.is_valid,
        validation_error=attempt.validation_error,
        executed=attempt.executed,
        rows=rows,
        execution_error=attempt.execution_error,
        prompt_tokens=sum(a.prompt_tokens for a in attempts),
        completion_tokens=sum(a.completion_tokens for a in attempts),
        timings=timings,
        attempts=attempts,
    )
