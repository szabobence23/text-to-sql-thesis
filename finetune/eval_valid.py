"""
Execution accuracy on the fine-tuning validation split: the 5 BIRD train
databases held out of training (build_sft_data.py), with exactly the
prompts of valid.jsonl (evidence and few-shot examples as drawn there).
A diagnostic of the fine-tuning on its own distribution, next to the
BIRD Mini-Dev and the own test sets: did the model get better at the
kind of question it was trained on, on databases it has not seen?

    python finetune/eval_valid.py --model qwen2.5-coder-7b-base-conv --run-name base-conv
    python finetune/eval_valid.py --model qwen2.5-coder-7b-ft --run-name ft
    python finetune/eval_valid.py --compare <result A> <result B>

Same path as the pipeline's first attempt: llm settings (temperature 0,
seed 42, num_ctx 8192), validate_sql, execution as the read-only role on
birdtrain_<db_id> (import_bird_train.py); the reference answer is the
valid.jsonl answer, executed the same way. Metrics from
evaluation.comparison (set EX = BIRD's, relaxed, strict). Writes
src/evaluation/results/<timestamp>_birdtrain-valid-en_<model>_<run-name>.json.
"""

import argparse
import datetime
import hashlib
import json
import os
import sys
import time
from collections import Counter

FINETUNE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(FINETUNE_DIR)
sys.path.append(os.path.join(REPO_DIR, "src"))

import llm
from database import execute_query, get_connection
from evaluation.comparison import is_order_sensitive, normalize_rows, relaxed_match, set_match, strict_match
from evaluation.compare import format_p, mcnemar_exact
from evaluation.evaluator import DEFAULT_OUTPUT_DIR, git_info
from sql_validator import validate_sql

from import_bird_train import DB_PREFIX

VALID_PATH = os.path.join(FINETUNE_DIR, "data", "sft", "valid.jsonl")
METRICS = ("set", "relaxed", "strict")


def load_examples(path=VALID_PATH):
    with open(path, encoding="utf-8") as file:
        return [json.loads(line) for line in file]


def score(expected, generated, ordered):
    """{metric: bool} for normalized rows; generated None = not executed."""
    if generated is None:
        return {metric: False for metric in METRICS}
    return {
        "set": set_match(expected, generated),
        "relaxed": relaxed_match(expected, generated, ordered),
        "strict": strict_match(expected, generated, ordered),
    }


def evaluate(example, conn, settings):
    user = example["messages"][1]["content"]
    reference_sql = llm.extract_sql(example["messages"][2]["content"])
    expected = normalize_rows(execute_query(conn, reference_sql))
    ordered = is_order_sensitive(reference_sql)

    start = time.perf_counter()
    generation = llm._chat([{"role": "user", "content": user}], settings)
    seconds = time.perf_counter() - start

    valid, error = validate_sql(conn, generation.sql)
    generated = None
    if valid:
        try:
            generated = normalize_rows(execute_query(conn, generation.sql))
        except Exception as exc:  # execution error (Postgres), recorded like the evaluator does
            error = str(exc).strip()
    return {
        "id": example["id"],
        "db_id": example["db_id"],
        "evidence_shown": example["evidence_shown"],
        "examples": len(example["examples"]),
        "reference_sql": reference_sql,
        "generated_sql": generation.sql,
        "valid_sql": valid,
        "executed": generated is not None,
        "error": error or None,
        **score(expected, generated, ordered),
        "prompt_tokens": generation.prompt_tokens,
        "generation_s": round(seconds, 3),
    }


def summary(results):
    def rates(rows):
        return {metric: sum(r[metric] for r in rows) for metric in METRICS} | {"total": len(rows)}

    groups = {
        "all": results,
        "evidence": [r for r in results if r["evidence_shown"]],
        "no_evidence": [r for r in results if not r["evidence_shown"]],
        "examples": [r for r in results if r["examples"]],
        "no_examples": [r for r in results if not r["examples"]],
    }
    out = {name: rates(rows) for name, rows in groups.items()}
    out["by_database"] = {db: rates([r for r in results if r["db_id"] == db])
                          for db in sorted({r["db_id"] for r in results})}
    return out


def compare(path_a, path_b):
    runs = []
    for path in (path_a, path_b):
        with open(path, encoding="utf-8") as file:
            runs.append(json.load(file))
    a, b = ({r["id"]: r for r in run["results"]} for run in runs)
    if set(a) != set(b):
        sys.exit("A két futás nem ugyanazokon a példákon készült")
    print(f"A = {runs[0]['run']['model']}, B = {runs[1]['run']['model']}, {len(a)} példa")
    for metric in METRICS:
        only_b = sum(b[i][metric] and not a[i][metric] for i in a)
        only_a = sum(a[i][metric] and not b[i][metric] for i in a)
        total_a = sum(r[metric] for r in a.values())
        total_b = sum(r[metric] for r in b.values())
        print(f"{metric:8} A {total_a:3}  B {total_b:3}  (B-ben +{only_b} / -{only_a}, "
              f"McNemar p = {format_p(mcnemar_exact(only_b, only_a))})")


def main():
    parser = argparse.ArgumentParser(description="EX a finomhangolás validációs adatbázisain")
    parser.add_argument("--model")
    parser.add_argument("--run-name")
    parser.add_argument("--limit", type=int, help="csak az első N példa (próbához)")
    parser.add_argument("--compare", nargs=2, metavar="RESULT", help="két eredményfájl összevetése")
    args = parser.parse_args()
    if args.compare:
        compare(*args.compare)
        return
    if not args.model or not args.run_name:
        parser.error("--model és --run-name kell (vagy --compare)")

    settings = llm.LLMSettings(model=args.model)
    examples = load_examples()[: args.limit]
    started_at = datetime.datetime.now()
    connections = {}
    results = []
    try:
        for index, example in enumerate(examples, start=1):
            db = example["db_id"]
            if db not in connections:
                connections[db] = get_connection(DB_PREFIX + db)
            results.append(evaluate(example, connections[db], settings))
            if index % 50 == 0 or index == len(examples):
                done = Counter(r["set"] for r in results)
                print(f"{index}/{len(examples)}  set EX {done[True]}/{index}", flush=True)
    finally:
        for conn in connections.values():
            conn.close()

    with open(VALID_PATH, "rb") as file:
        valid_sha256 = hashlib.sha256(file.read()).hexdigest()
    out = {
        "run": {
            "started_at": started_at.isoformat(timespec="seconds"),
            "git": git_info(),
            "model": args.model,
            "model_digest": llm.model_digest(args.model),
            "llm": {"temperature": settings.temperature, "seed": settings.seed, "num_ctx": settings.num_ctx},
            "valid_sha256": valid_sha256,
            "limit": args.limit,
        },
        "summary": summary(results),
        "results": results,
    }
    stamp = started_at.strftime("%Y%m%d-%H%M%S")
    slug = args.model.replace(":", "-").replace("/", "-")
    path = os.path.join(DEFAULT_OUTPUT_DIR, f"{stamp}_birdtrain-valid-en_{slug}_{args.run_name}.json")
    with open(path, "w", encoding="utf-8") as file:
        json.dump(out, file, ensure_ascii=False, indent=1)
    s = out["summary"]["all"]
    print(f"set {s['set']}/{s['total']}, relaxed {s['relaxed']}, strict {s['strict']}")
    print(path)


if __name__ == "__main__":
    main()
