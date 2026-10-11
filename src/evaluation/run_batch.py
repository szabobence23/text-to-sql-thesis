"""
Run the evaluator for several datasets and languages, repeated, then
summarize the runs with report.py.

    python src/evaluation/run_batch.py --run-name baseline2
    python src/evaluation/run_batch.py --run-name javitas2 --correction-rounds 2

Options the batch does not know (e.g. --correction-rounds, --no-schema-hints,
--model) are passed to every evaluator run unchanged. Each run is a normal
evaluator run with its own result file, named <run-name>-r<repeat>.

Repeats go round by round (every dataset and language once, then again),
so a slow drift on the machine does not hit one configuration only.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import time

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(SRC_DIR)

from dataset_loader import available_datasets
from evaluation.evaluator import DEFAULT_OUTPUT_DIR, git_info
from evaluation.report import load_runs, print_summary, summarize


EVALUATOR = os.path.join(SRC_DIR, "evaluation", "evaluator.py")
DEFAULT_DATASETS = ["olist", "f1", "adventureworks"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Kiértékelések sorozatban: datasetek × nyelvek × ismétlések"
    )
    parser.add_argument("--run-name", required=True, help="a sorozat neve, pl. baseline2")
    parser.add_argument("--datasets", nargs="+", default=DEFAULT_DATASETS, choices=available_datasets())
    parser.add_argument("--languages", nargs="+", default=["hu", "en"])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="futtatás commitolatlan kóddal is (az eredmény nem reprodukálható a commitból)",
    )
    # Everything else goes to the evaluator as is.
    return parser.parse_known_args()


def run_one(dataset, language, run_name, extra_args):
    """One evaluator run; returns the path of its result file."""
    command = [
        sys.executable, EVALUATOR,
        "--dataset", dataset,
        "--language", language,
        "--run-name", run_name,
        *extra_args,
    ]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env)

    if result.returncode != 0:
        print(result.stdout[-2000:])
        print(result.stderr[-2000:])
        raise SystemExit(f"Az evaluator hibával leállt: {dataset} {language} {run_name}")

    # The evaluator prints the result path as its last line.
    path = result.stdout.strip().splitlines()[-1].strip()
    if not path.endswith(".json") or not os.path.exists(path):
        raise SystemExit(f"Nem található az eredményfájl a kimenetben: {path}")
    return path


def main():
    args, extra_args = parse_args()

    git = git_info()
    if git["dirty"] and not args.allow_dirty:
        raise SystemExit(
            "Commitolatlan változások vannak a kódban vagy a tesztkészletekben, "
            "így az eredmények nem reprodukálhatók a commitból. Commitolj, vagy "
            "add meg az --allow-dirty kapcsolót."
        )

    plan = [
        (repeat, dataset, language)
        for repeat in range(1, args.repeats + 1)
        for dataset in args.datasets
        for language in args.languages
    ]

    started_at = datetime.datetime.now()
    print(
        f"Sorozat: {args.run_name}, {len(plan)} futás "
        f"({len(args.datasets)} dataset × {len(args.languages)} nyelv × {args.repeats} ismétlés), "
        f"commit {git['commit'][:7]}"
        + (" (commitolatlan változásokkal)" if git["dirty"] else "")
    )
    if extra_args:
        print(f"Evaluator kapcsolók: {' '.join(extra_args)}")

    paths = []
    for index, (repeat, dataset, language) in enumerate(plan, start=1):
        start = time.perf_counter()
        path = run_one(dataset, language, f"{args.run_name}-r{repeat}", extra_args)
        paths.append(path)

        with open(path, encoding="utf-8") as file:
            summary = json.load(file)["summary"]
        relaxed = summary["relaxed_ex"]
        print(
            f"[{index:>2}/{len(plan)}] {dataset:15} {language} r{repeat}  "
            f"relaxed {relaxed['count']}/{relaxed['total']} ({relaxed['rate']:.1%})  "
            f"{time.perf_counter() - start:5.0f} s"
        )

    print("\n" + "=" * 80)
    print("ÖSSZESÍTÉS")
    print("=" * 80)
    summary = summarize(load_runs(paths))
    print_summary(summary)

    stamp = started_at.strftime("%Y%m%d-%H%M%S")
    output = os.path.join(DEFAULT_OUTPUT_DIR, f"{stamp}_batch_{args.run_name}.json")
    with open(output, "w", encoding="utf-8") as file:
        json.dump(
            {
                "batch": {
                    "run_name": args.run_name,
                    "started_at": started_at.isoformat(timespec="seconds"),
                    "git": git,
                    "evaluator_args": extra_args,
                    "files": [os.path.basename(p) for p in paths],
                },
                "summary": summary,
            },
            file,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\nÖsszesítés mentve:\n{output}")


if __name__ == "__main__":
    main()
