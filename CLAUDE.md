# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

BSc thesis (BME): text-to-SQL with a local LLM (Ollama, `qwen2.5-coder:7b`) translating natural-language questions — mostly **Hungarian** — into PostgreSQL queries — main dataset: Brazilian **Olist e-commerce**, but databases are swappable (see Datasets) — and **measuring the effectiveness** of different approaches. Planned extensions: RAG, MCP, fine-tuning, more languages, more validation, natural-language answers. Console output is in Hungarian; keep that convention.

Because the thesis is about measurement, changes that affect what the model sees (prompt text, schema text, dataset hints, LLM options) change results and must be treated as a new experimental configuration, not a refactor.

## Environment & commands

Windows machine; use the project venv (`.venv\Scripts\python.exe`). `pip install -r requirements.txt`.

Runtime services:
- **PostgreSQL** (`docker compose up -d`, container `text-to-sql-postgres`, `./datasets` mounted at `/datasets`), one database per dataset. The app connects as the read-only role `text2sql_reader`; server/credentials from `TEXT2SQL_DB_*` env vars (see `src/database.py`), the database name from the dataset.
- **Ollama** with `qwen2.5-coder:7b` pulled.

## Datasets

A dataset = one folder in `datasets/<name>/` (`dataset.json` with `db_name`, `schema.sql`, `import.sql`, optional `hints.txt`, `test_cases/<language>.json`, gitignored `data/`); details in `datasets/README.md`. Selected by `--dataset` or `TEXT2SQL_DATASET` (default `olist`); `sales` is a toy smoke-test/template. Test-question language is selected by `--language` or `TEXT2SQL_LANGUAGE` (default `hu`); only the questions are translated, the prompt stays the same. A translation must be identical to `hu.json` except for `question` (same ids, order, ground truths), otherwise results across languages are not comparable. `src/dataset_loader.py` is the only code that knows the folder layout (deliberately not named `datasets.py`, which would shadow the Hugging Face package). Nothing dataset-specific belongs in `src/`.

Setup: `python database/setup_dataset.py <name> [--recreate]` runs psql in the container: create DB → `schema.sql` → `import.sql` → `database/readonly_role.sql` (psql var `db_name`; one `text2sql_reader` role for the server, SELECT-only, read-only transactions, 10s timeout). `src/tests/test_datasets.py` checks every dataset folder is complete (including a default-language test file), every language's ground truths pass the structural validator, and translations differ only in `question`.

Run from the repo root:
- Demo: `python src/main.py ["kérdés"] [--dataset <name>]` (default question is for Olist)
- Evaluation: `python src/evaluation/evaluator.py --run-name <name>` (also `--dataset`, `--language`, `--correction-rounds`, `--no-schema-hints`, `--model`, `--temperature`, `--seed`, `--num-ctx`, `--cases` which overrides the language file). Each run writes a new file `src/evaluation/results/<timestamp>_<dataset>-<language>_<model>_<name>.json` (older results lack the language or the dataset in the name) with the full `PipelineConfig`, git commit/dirty flag, model digest, prompt/schema/test-case hashes and the exact schema text. `qwen_baseline.json` is the old-format v1 result.
- Tests: `python -m pytest` (config in `pyproject.toml` puts `src/` on the path; tests import modules flat, e.g. `from llm import extract_sql`). Offline only: `python -m pytest -m "not db"`. Single test: `python -m pytest src/tests/test_comparison.py -k relaxed`.

## Architecture

`pipeline.run_pipeline(conn, question, schema, PipelineConfig)` is the single code path used by both `main.py` and the evaluator: generate → validate → execute (invalid SQL is never executed) → if validation or execution failed, up to `max_correction_rounds` corrections. It returns a `PipelineResult` (top-level fields = final attempt, tokens/timings = totals, `attempts` = every try) and prints nothing; front-ends (CLI, evaluator, future MCP server) only format it.

`PipelineConfig` holds every feature switch; defaults reproduce the baseline (correction off in the evaluator; `main.py` demo uses 2 rounds). New features get a switch here, off by default, and only once they actually work. Connection and schema must come from `pipeline.open_connection(config)` / `pipeline.load_schema(conn, config)` so database, schema text and hints all match `config.dataset`.

- `schema.py` builds the prompt's schema text from `information_schema.columns` plus FK relationships from **`pg_catalog.pg_constraint`** (not `information_schema.constraint_column_usage`, which hides FKs from non-owner roles like `text2sql_reader`), then appends the dataset's `hints.txt` (switch: `schema_hints`).
- `llm.py`: `PROMPT_TEMPLATE` (hashed into `PROMPT_SHA256` for results), `LLMSettings` (temperature 0, fixed seed, explicit `num_ctx` because Ollama silently truncates longer prompts), `extract_sql` for code-fence stripping. `correct_sql` continues the same conversation (baseline prompt, the failed answer, `CORRECTION_TEMPLATE` with the Postgres error), so the first-attempt prompt is unchanged; both templates are hashed into results. Even at temperature 0 Ollama is not fully deterministic across calls (GPU / prompt-cache effects), so compare configurations over repeated runs.
- Validation, combined in `sql_validator.validate_sql(conn, sql)`; the order matters because stage 2 interpolates SQL into `PREPARE`:
  1. `sql_structural_validator.validate_sql_structure(sql)` — offline sqlglot check: one statement, a `Query`, no DML/DDL anywhere in the tree, no `SELECT INTO`, no locking clauses. Does not filter functions (`pg_sleep` etc.).
  2. `sql_schema_validator.validate_sql_schema(conn, sql)` — `PREPARE`/`DEALLOCATE` so Postgres checks names and types without executing.
- Security relies on the DB role, not the validators. `database.execute_query` and the validators always **roll back** (never commit), so session changes made by a generated query (e.g. `set_config`) cannot leak into the next question.
- `evaluation/comparison.py` defines the metrics: **strict EX** (same rows and columns) and **relaxed EX** (all ground-truth columns present among generated columns, extra columns allowed). Row order counts only if the ground truth has a top-level `ORDER BY`; numbers are rounded to 4 decimals. The evaluator executes all ground truths before calling the LLM and fails fast if one is broken. Since correction only runs after a failed first attempt, a run with correction also reports `first_attempt` metrics, i.e. the same run without correction.
- Olist pitfall: `customer_id` is per order; a real customer is `customer_unique_id`.
