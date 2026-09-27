import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

# src könyvtár elérhetővé tétele
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(SRC_DIR)

import ollama

from database import DB_NAME, DB_USER, execute_query, get_connection
from evaluation.comparison import (
    is_order_sensitive,
    normalize_rows,
    relaxed_match,
    strict_match,
)
from llm import PROMPT_SHA256, LLMSettings
from pipeline import PipelineConfig, load_schema, run_pipeline


EVAL_DIR = os.path.join(SRC_DIR, "evaluation")
DEFAULT_CASES = os.path.join(EVAL_DIR, "test_cases.json")
DEFAULT_OUTPUT_DIR = os.path.join(EVAL_DIR, "results")


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_info():
    def git(*args):
        return subprocess.run(
            ["git", *args],
            cwd=SRC_DIR,
            capture_output=True,
            text=True,
        ).stdout.strip()

    try:
        return {
            "commit": git("rev-parse", "HEAD"),
            # Uncommitted changes mean the commit alone does not
            # reproduce this run.
            "dirty": bool(git("status", "--porcelain")),
        }
    except OSError:
        return {"commit": None, "dirty": None}


def model_digest(model):
    # The tag (e.g. qwen2.5-coder:7b) can point to new weights after
    # a re-pull; the digest identifies the exact model evaluated.
    for m in ollama.list().models:
        if m.model == model:
            return m.digest
    return None


def run_ground_truths(conn, test_cases):
    """
    Execute every ground-truth query up front, so a broken test case
    stops the run before any time is spent on the LLM.
    """
    expected = {}

    for case in test_cases:
        try:
            expected[case["id"]] = normalize_rows(
                execute_query(conn, case["ground_truth_sql"])
            )
        except Exception as e:
            raise RuntimeError(
                f"Ground truth of test case {case['id']} failed: {e}"
            ) from e

    return expected


def evaluate_test_case(conn, schema, config, case, expected_rows):
    ordered = is_order_sensitive(case["ground_truth_sql"])

    result = run_pipeline(conn, case["question"], schema, config)

    generated_rows = (
        normalize_rows(result.rows) if result.executed else None
    )

    if generated_rows is None:
        strict = relaxed = False
    else:
        strict = strict_match(expected_rows, generated_rows, ordered)
        relaxed = relaxed_match(expected_rows, generated_rows, ordered)

    return {
        "id": case["id"],
        "question": case["question"],
        "category": case["category"],
        "difficulty": case["difficulty"],
        "ground_truth_sql": case["ground_truth_sql"],
        "order_sensitive": ordered,
        "expected_result": expected_rows,
        "generated_sql": result.sql,
        "raw_response": result.raw_response,
        "valid_sql": result.is_valid,
        "validation_error": result.validation_error,
        "execution_success": result.executed,
        "execution_error": result.execution_error,
        "generated_result": generated_rows,
        "strict_match": strict,
        "relaxed_match": relaxed,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "timings": result.timings,
    }


def summarize(results):
    total = len(results)

    def rate(key, subset=results):
        n = len(subset)
        hits = sum(r[key] for r in subset)
        return {"count": hits, "total": n, "rate": hits / n if n else 0}

    def mean(values):
        values = list(values)
        return sum(values) / len(values) if values else 0

    def breakdown(field):
        groups = defaultdict(list)
        for r in results:
            groups[r[field]].append(r)
        return {
            name: {
                "strict_ex": rate("strict_match", group),
                "relaxed_ex": rate("relaxed_match", group),
            }
            for name, group in sorted(groups.items())
        }

    return {
        "total_questions": total,
        "valid_sql": rate("valid_sql"),
        "execution_success": rate("execution_success"),
        "strict_ex": rate("strict_match"),
        "relaxed_ex": rate("relaxed_match"),
        "by_category": breakdown("category"),
        "by_difficulty": breakdown("difficulty"),
        "mean_generation_s": mean(r["timings"]["generation_s"] for r in results),
        "mean_prompt_tokens": mean(r["prompt_tokens"] for r in results),
        "mean_completion_tokens": mean(r["completion_tokens"] for r in results),
    }


def output_path(output_dir, started_at, model, run_name):
    stamp = started_at.strftime("%Y%m%d-%H%M%S")
    model_slug = re.sub(r"[^A-Za-z0-9.]+", "-", model)
    name = f"{stamp}_{model_slug}"
    if run_name:
        name += f"_{run_name}"
    return os.path.join(output_dir, f"{name}.json")


def parse_args():
    defaults = LLMSettings()

    parser = argparse.ArgumentParser(description="Text-to-SQL kiértékelés")
    parser.add_argument("--model", default=defaults.model)
    parser.add_argument("--temperature", type=float, default=defaults.temperature)
    parser.add_argument("--seed", type=int, default=defaults.seed)
    parser.add_argument("--num-ctx", type=int, default=defaults.num_ctx)
    parser.add_argument(
        "--no-schema-hints",
        action="store_true",
        help="a kézzel írt adatbázis-megjegyzések nélkül",
    )
    parser.add_argument("--cases", default=DEFAULT_CASES)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-name", default="", help="rövid név a fájlnévbe, pl. baseline")
    return parser.parse_args()


def print_rate(label, stats):
    print(f"{label}: {stats['count']}/{stats['total']} ({stats['rate']:.1%})")


def main():
    args = parse_args()

    llm_settings = LLMSettings(
        model=args.model,
        temperature=args.temperature,
        seed=args.seed,
        num_ctx=args.num_ctx,
    )

    config = PipelineConfig(
        llm=llm_settings,
        schema_hints=not args.no_schema_hints,
    )

    with open(args.cases, "r", encoding="utf-8") as file:
        cases_text = file.read()
    test_cases = json.loads(cases_text)

    started_at = datetime.datetime.now()

    conn = get_connection()

    try:
        schema = load_schema(conn, config)
        expected = run_ground_truths(conn, test_cases)

        print(f"Olist séma betöltve, {len(test_cases)} teszteset, modell: {config.llm.model}")

        results = []

        for case in test_cases:
            result = evaluate_test_case(
                conn, schema, config, case, expected[case["id"]]
            )
            results.append(result)

            if result["relaxed_match"]:
                status = "HELYES" if result["strict_match"] else "HELYES (relaxed)"
            elif not result["valid_sql"]:
                status = "ÉRVÉNYTELEN SQL"
            elif not result["execution_success"]:
                status = "VÉGREHAJTÁSI HIBA"
            else:
                status = "ROSSZ EREDMÉNY"

            print(f"[{case['id']:>3}] {status:<18} {case['question']}")

            if result["prompt_tokens"] >= config.llm.num_ctx:
                print(f"      FIGYELEM: a prompt elérte a num_ctx határt ({config.llm.num_ctx}), csonkolás lehetséges")

    finally:
        conn.close()

    summary = summarize(results)

    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY")
    print("=" * 80)
    print_rate("Érvényes SQL", summary["valid_sql"])
    print_rate("Sikeres végrehajtás", summary["execution_success"])
    print_rate("Execution accuracy (strict)", summary["strict_ex"])
    print_rate("Execution accuracy (relaxed)", summary["relaxed_ex"])
    print(f"Átlagos generálási idő: {summary['mean_generation_s']:.2f} s")

    output = {
        "run": {
            "started_at": started_at.isoformat(timespec="seconds"),
            "git": git_info(),
            "pipeline": config.to_dict(),
            "model_digest": model_digest(config.llm.model),
            "prompt_sha256": PROMPT_SHA256,
            "database": DB_NAME,
            "db_user": DB_USER,
            "test_cases_file": os.path.relpath(args.cases, SRC_DIR),
            "test_cases_sha256": sha256(cases_text),
            "schema_sha256": sha256(schema),
            "schema_text": schema,
        },
        "summary": summary,
        "results": results,
    }

    os.makedirs(args.output_dir, exist_ok=True)
    path = output_path(args.output_dir, started_at, config.llm.model, args.run_name)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2, default=str)

    print("\nEredmények mentve:")
    print(path)


if __name__ == "__main__":
    main()
