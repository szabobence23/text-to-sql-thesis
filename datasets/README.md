# Datasets

Each folder is one database with everything that belongs to it. The pipeline
selects one by name (`--dataset <name>`, or the `TEXT2SQL_DATASET` env var;
default `olist`).

```
<name>/
  dataset.json      {"name", "db_name", "description"}
  schema.sql        CREATE TABLE statements, with foreign keys
  import.sql        data loading (COPY from /datasets/<name>/data/... or INSERTs)
  hints.txt         optional hand-written notes appended to the schema in the prompt
  test_cases/       one file per question language: hu.json (required), en.json, ...
                    [{"id", "question", "category", "difficulty", "ground_truth_sql"}]
                    translations must match hu.json except for "question"
  attacks.json      optional hand-written attack SQL for src/evaluation/attack_evaluator.py
                    [{"id", "category", "description", "sql", "expected_layer"}]
                    expected_layer: structure | function | schema | database | none
  data/             data files (gitignored *.csv)
```

## Adding a dataset

1. Create the folder with the files above (`sales/` is a minimal example).
   Declare foreign keys in `schema.sql`: the prompt lists them as relationships.
2. `python database/setup_dataset.py <name>` creates the database in the
   docker container, loads schema and data, and grants the read-only role.
   `--recreate` drops and rebuilds an existing one.
3. `python -m pytest src/tests/test_datasets.py` checks the folder is complete
   and every ground truth passes the structural validator.
4. `python src/evaluation/evaluator.py --dataset <name>`

Ground truths with `LIMIT` must not have ties at the cut-off, otherwise the
expected result is arbitrary. Only PostgreSQL is supported; datasets from
SQLite benchmarks (Spider, BIRD) must be converted first.

## Datasets

- `olist`: Brazilian e-commerce (Kaggle), the main thesis dataset. The CSVs
  are not in git; download them into `olist/data/`.
- `sales`: 4-table toy schema, smoke test and template.
