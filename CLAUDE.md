# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

BSc thesis (BME): text-to-SQL with a local LLM (Ollama, `qwen2.5-coder:7b`) translating natural-language questions — mostly **Hungarian** — into PostgreSQL queries over the Brazilian **Olist e-commerce** dataset, and **measuring the effectiveness** of different approaches. Planned extensions: RAG, MCP, fine-tuning, more languages, more validation, natural-language answers. Console output is in Hungarian; keep that convention.

Because the thesis is about measurement, changes that affect what the model sees (prompt text, schema text, LLM options) change results and must be treated as a new experimental configuration, not a refactor.

## Environment & commands

Windows machine; use the project venv (`.venv\Scripts\python.exe`). `pip install -r requirements.txt`.

Runtime services:
- **PostgreSQL** (`docker compose up`, container `text-to-sql-postgres`), db `olist_db`. The app connects as the read-only role `text2sql_reader`; connection settings come from `TEXT2SQL_DB_*` env vars (see `src/database.py`).
- **Ollama** with `qwen2.5-coder:7b` pulled.

Database setup is manual. `docker-compose.yml` sets `POSTGRES_DB=sales_db` and auto-runs `database/init.sql`, a **legacy toy schema** unrelated to the code. For `olist_db`, run with `psql -U postgres -d olist_db` inside the container, in order:
1. `database/olist_schema.sql` (tables + FKs)
2. `database/import_olist.sql` (`COPY` from `/data/olist/*.csv`, mounted from the gitignored `database/olist/`)
3. `database/readonly_role.sql` (creates `text2sql_reader`: SELECT-only, read-only transactions, 10s statement timeout)

Run from the repo root:
- Demo: `python src/main.py` (question hardcoded in `main()`)
- Evaluation: `python src/evaluation/evaluator.py --run-name <name>` (also `--model`, `--temperature`, `--seed`, `--num-ctx`, `--cases`). Each run writes a new file `src/evaluation/results/<timestamp>_<model>_<name>.json` with the full config, git commit/dirty flag, model digest, prompt/schema/test-case hashes and the exact schema text. `qwen_baseline.json` is the old-format v1 result.
- Tests: `python -m pytest` (config in `pyproject.toml` puts `src/` on the path; tests import modules flat, e.g. `from llm import extract_sql`). Offline only: `python -m pytest -m "not db"`. Single test: `python -m pytest src/tests/test_comparison.py -k relaxed`.

## Architecture

`pipeline.run_pipeline(conn, question, schema, LLMSettings)` is the single code path used by both `main.py` and the evaluator: generate → validate → execute (invalid SQL is never executed). It returns a `PipelineResult` dataclass and prints nothing; front-ends (CLI, evaluator, future MCP server) only format it.

- `schema.py` builds the prompt's schema text from `information_schema.columns` plus FK relationships from **`pg_catalog.pg_constraint`** (not `information_schema.constraint_column_usage`, which hides FKs from non-owner roles like `text2sql_reader`), then appends hand-written dataset hints.
- `llm.py`: `PROMPT_TEMPLATE` (hashed into `PROMPT_SHA256` for results), `LLMSettings` (temperature 0, fixed seed, explicit `num_ctx` because Ollama silently truncates longer prompts), `extract_sql` for code-fence stripping. Even at temperature 0 Ollama is not fully deterministic across calls (GPU / prompt-cache effects), so compare configurations over repeated runs.
- Validation, combined in `sql_validator.validate_sql(conn, sql)`; the order matters because stage 2 interpolates SQL into `PREPARE`:
  1. `sql_structural_validator.validate_sql_structure(sql)` — offline sqlglot check: one statement, a `Query`, no DML/DDL anywhere in the tree, no `SELECT INTO`, no locking clauses. Does not filter functions (`pg_sleep` etc.).
  2. `sql_schema_validator.validate_sql_schema(conn, sql)` — `PREPARE`/`DEALLOCATE` so Postgres checks names and types without executing.
- Security relies on the DB role, not the validators. `database.execute_query` and the validators always **roll back** (never commit), so session changes made by a generated query (e.g. `set_config`) cannot leak into the next question.
- `evaluation/comparison.py` defines the metrics: **strict EX** (same rows and columns) and **relaxed EX** (all ground-truth columns present among generated columns, extra columns allowed). Row order counts only if the ground truth has a top-level `ORDER BY`; numbers are rounded to 4 decimals. The evaluator executes all ground truths before calling the LLM and fails fast if one is broken.
- `test_cases.json` fields: `id, question, category, difficulty, ground_truth_sql`. Olist pitfall: `customer_id` is per order; a real customer is `customer_unique_id`.
