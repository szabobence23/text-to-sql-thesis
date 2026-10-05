"""
Attack evaluation: runs the dataset's attacks.json through the defence
layers of the pipeline and records which layer stopped each attack.

No LLM is involved: the attacks are hand-written SQL, so the result is
deterministic and shows what the defences do regardless of the model.
"""

import argparse
import datetime
import json
import os
import sys
import time

# src library
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(SRC_DIR)

import psycopg

from database import DB_USER, execute_query
from dataset_loader import DEFAULT_DATASET, REPO_DIR, available_datasets, load_dataset
from evaluation.evaluator import DEFAULT_OUTPUT_DIR, git_info, sha256
from pipeline import PipelineConfig, open_connection
from sql_function_validator import BLOCKED_FUNCTIONS, validate_sql_functions
from sql_schema_validator import validate_sql_schema
from sql_structural_validator import validate_sql_structure


# "none": every layer let the attack through and it executed.
LAYERS = ["structure", "function", "schema", "database", "none"]

LAYER_LABELS = {
    "structure": "strukturális",
    "function": "függvény-tiltólista",
    "schema": "séma",
    "database": "adatbázis",
    "none": "ÁTJUTOTT",
}


def find_stopping_layer(conn, sql, block_functions):
    """
    (layer, error) for the first layer that rejected sql, or
    ("none", "") if it executed. Same order as sql_validator.validate_sql,
    followed by execution as the read-only role.
    """
    is_valid, error = validate_sql_structure(sql)
    if not is_valid:
        return "structure", error

    if block_functions:
        is_valid, error = validate_sql_functions(sql)
        if not is_valid:
            return "function", error

    is_valid, error = validate_sql_schema(conn, sql)
    if not is_valid:
        return "schema", error

    try:
        execute_query(conn, sql)
    except psycopg.Error as e:
        return "database", str(e).strip()

    return "none", ""


def output_path(output_dir, started_at, dataset, run_name):
    stamp = started_at.strftime("%Y%m%d-%H%M%S")
    name = f"{stamp}_{dataset}-attacks"
    if run_name:
        name += f"_{run_name}"
    return os.path.join(output_dir, f"{name}.json")


def parse_args():
    parser = argparse.ArgumentParser(description="Támadó lekérdezések kiértékelése")
    parser.add_argument(
        "--dataset",
        default=DEFAULT_DATASET,
        choices=available_datasets(),
        help="a datasets/<dataset>/attacks.json támadásai",
    )
    parser.add_argument(
        "--no-function-blocklist",
        action="store_true",
        help="a függvény-tiltólista nélkül: mi állítja meg ekkor a támadásokat?",
    )
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-name", default="", help="rövid név a fájlnévbe")
    return parser.parse_args()


def main():
    args = parse_args()

    config = PipelineConfig(
        dataset=args.dataset,
        block_functions=not args.no_function_blocklist,
    )

    dataset = load_dataset(config.dataset)

    if not os.path.exists(dataset.attacks_path):
        sys.exit(f"A '{dataset.name}' datasetnek nincs attacks.json fájlja.")

    with open(dataset.attacks_path, "r", encoding="utf-8") as file:
        attacks_text = file.read()
    attacks = json.loads(attacks_text)

    started_at = datetime.datetime.now()
    blocklist_label = "be" if config.block_functions else "KI"

    print(
        f"Támadások: {dataset.name} ({len(attacks)} db), "
        f"függvény-tiltólista: {blocklist_label}\n"
    )

    results = []
    conn = open_connection(config)

    try:
        for attack in attacks:
            start = time.perf_counter()
            layer, error = find_stopping_layer(conn, attack["sql"], config.block_functions)
            seconds = time.perf_counter() - start

            # An attack may break the session (e.g. a cancelled backend);
            # the next one must not fail because of that.
            if conn.broken:
                conn = open_connection(config)

            as_expected = layer == attack["expected_layer"]

            results.append({
                "id": attack["id"],
                "category": attack["category"],
                "description": attack["description"],
                "sql": attack["sql"],
                "expected_layer": attack["expected_layer"],
                "stopped_by": layer,
                "as_expected": as_expected,
                "error": error,
                "seconds": seconds,
            })

            mark = "" if as_expected else f"  (várt: {LAYER_LABELS[attack['expected_layer']]})"
            print(
                f"[{attack['id']:>3}] {LAYER_LABELS[layer]:<20} "
                f"{attack['description']}{mark}"
            )

    finally:
        conn.close()

    by_layer = {layer: sum(r["stopped_by"] == layer for r in results) for layer in LAYERS}
    got_through = [r["id"] for r in results if r["stopped_by"] == "none"]

    summary = {
        "total": len(results),
        "by_layer": by_layer,
        "as_expected": sum(r["as_expected"] for r in results),
        "got_through": got_through,
    }

    print("\n" + "=" * 80)
    print("ÖSSZESÍTÉS")
    print("=" * 80)
    for layer in LAYERS:
        print(f"{LAYER_LABELS[layer]:<20} {by_layer[layer]}")
    print(f"\nA várt réteg állította meg: {summary['as_expected']}/{summary['total']}")
    if got_through:
        print(f"Átjutott (lefutott): {', '.join(map(str, got_through))}")

    output = {
        "run": {
            "started_at": started_at.isoformat(timespec="seconds"),
            "git": git_info(),
            "dataset": dataset.name,
            "database": dataset.db_name,
            "db_user": DB_USER,
            "block_functions": config.block_functions,
            "blocked_functions": sorted(BLOCKED_FUNCTIONS) if config.block_functions else [],
            "attacks_file": os.path.relpath(dataset.attacks_path, REPO_DIR),
            "attacks_sha256": sha256(attacks_text),
        },
        "summary": summary,
        "results": results,
    }

    os.makedirs(args.output_dir, exist_ok=True)
    path = output_path(args.output_dir, started_at, dataset.name, args.run_name)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    print("\nEredmények mentve:")
    print(path)


if __name__ == "__main__":
    main()
