"""
Summarize repeated evaluation runs: mean and standard deviation per
dataset, language and configuration.

    python src/evaluation/report.py src/evaluation/results/*_baseline2-r*.json

Ollama is not fully deterministic even at temperature 0, so a single run
is not enough to compare configurations. Repeats of the same setup are
grouped, and questions whose outcome changed between repeats are counted.
"""

import argparse
import glob
import json
import os
import statistics
from collections import defaultdict


RATES = [
    ("valid_sql", "Érvényes SQL"),
    ("strict_ex", "Strict EX"),
    ("relaxed_ex", "Relaxed EX"),
]

DIFFICULTIES = ["easy", "medium", "hard"]

# Runs grouped together must agree on these, or they are not repeats
# of one setup (different prompt, test set, schema or model weights).
MUST_MATCH = ["prompt_sha256", "test_cases_sha256", "schema_sha256", "model_digest"]


def load_runs(paths):
    """Evaluator result files; anything else (e.g. batch summaries) is skipped."""
    runs = []
    for path in paths:
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
        if "run" in data and "results" in data:
            data["_path"] = path
            runs.append(data)
    return runs


def setup_label(pipeline):
    llm = pipeline["llm"]
    parts = [
        f"javítás={pipeline['max_correction_rounds']}",
        f"hintek={'be' if pipeline['schema_hints'] else 'ki'}",
        llm["model"],
    ]
    if pipeline.get("column_values"):
        parts.append(f"értékek≤{pipeline['column_values_max']}")
    retrieval = pipeline.get("schema_retrieval", "full")
    if retrieval != "full":
        parts.append(f"séma={retrieval}")
    if retrieval in ("bm25", "dense", "hybrid"):
        parts.append(f"k={pipeline['retrieval_k']}")
        if not pipeline.get("retrieval_fk_expansion", True):
            parts.append("FK=ki")
        if pipeline.get("retrieval_descriptions"):
            parts.append("leírások")
        if pipeline.get("translate_for_retrieval"):
            parts.append("fordítás")
        if pipeline.get("table_selection"):
            parts.append("szűrés")
            if pipeline.get("table_selection_style", "strict") != "strict":
                parts.append(pipeline["table_selection_style"])
            if pipeline.get("selection_keep_top"):
                parts.append(f"top{pipeline['selection_keep_top']}-marad")
    if llm["temperature"]:
        parts.append(f"temp={llm['temperature']}")
    if not pipeline.get("block_functions", True):
        parts.append("tiltólista=ki")
    return " ".join(parts)


def group_key(run):
    meta = run["run"]
    return (
        meta["pipeline"]["dataset"],
        meta.get("test_cases_language") or "?",
        setup_label(meta["pipeline"]),
    )


def mean_std(values):
    mean = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    return mean, std


def summarize_group(runs):
    rates = {}
    for key, _ in RATES:
        values = [r["summary"][key]["rate"] for r in runs]
        rates[key] = mean_std(values)

    by_difficulty = {}
    for difficulty in DIFFICULTIES:
        values = []
        for r in runs:
            cases = [c for c in r["results"] if c["difficulty"] == difficulty]
            if cases:
                values.append(sum(c["relaxed_match"] for c in cases) / len(cases))
        if values:
            by_difficulty[difficulty] = mean_std(values)

    # A question is unstable if its relaxed outcome differs between repeats.
    outcomes = defaultdict(set)
    for r in runs:
        for c in r["results"]:
            outcomes[c["id"]].add(c["relaxed_match"])
    unstable = sorted(i for i, seen in outcomes.items() if len(seen) > 1)

    mismatched = [
        field for field in MUST_MATCH
        if len({r["run"].get(field) for r in runs}) > 1
    ]

    return {
        "runs": len(runs),
        "questions": runs[0]["summary"]["total_questions"],
        "rates": {k: {"mean": m, "std": s} for k, (m, s) in rates.items()},
        "relaxed_by_difficulty": {k: {"mean": m, "std": s} for k, (m, s) in by_difficulty.items()},
        "unstable_questions": unstable,
        "mean_generation_s": statistics.mean(r["summary"]["mean_generation_s"] for r in runs),
        "mean_prompt_tokens": statistics.mean(r["summary"]["mean_prompt_tokens"] for r in runs),
        "dirty_runs": sum(bool(r["run"]["git"].get("dirty")) for r in runs),
        "mismatched_fields": mismatched,
        "files": [os.path.basename(r["_path"]) for r in runs],
    }


def summarize(runs):
    groups = defaultdict(list)
    for run in runs:
        groups[group_key(run)].append(run)

    return [
        {"dataset": d, "language": l, "setup": s, **summarize_group(rs)}
        for (d, l, s), rs in sorted(groups.items())
    ]


def fmt(stat):
    return f"{stat['mean']:6.1%} ± {stat['std']:4.1%}"


def print_summary(summary):
    print(f"{'Dataset':15} {'Nyelv':5} {'Futás':>5}  "
          + "  ".join(f"{label:>15}" for _, label in RATES)
          + f"  {'Ingadozó':>8}  {'Gen. idő':>8}  Beállítás")

    for g in summary:
        print(f"{g['dataset']:15} {g['language']:5} {g['runs']:>5}  "
              + "  ".join(f"{fmt(g['rates'][key]):>15}" for key, _ in RATES)
              + f"  {len(g['unstable_questions']):>8}  {g['mean_generation_s']:7.2f}s  {g['setup']}")

    print("\nRelaxed EX nehézség szerint:")
    for g in summary:
        parts = "  ".join(
            f"{d} {fmt(g['relaxed_by_difficulty'][d])}"
            for d in DIFFICULTIES if d in g["relaxed_by_difficulty"]
        )
        print(f"  {g['dataset']:15} {g['language']:5} {parts}")

    warnings = []
    for g in summary:
        name = f"{g['dataset']} {g['language']} ({g['setup']})"
        if g["mismatched_fields"]:
            warnings.append(f"{name}: a futások nem ugyanazzal mértek: {', '.join(g['mismatched_fields'])}")
        if g["dirty_runs"]:
            warnings.append(f"{name}: {g['dirty_runs']} futás commitolatlan kóddal készült")
        if g["runs"] < 2:
            warnings.append(f"{name}: csak 1 futás, nincs szórás")
    if warnings:
        print("\nFIGYELEM:")
        for w in warnings:
            print(f"  - {w}")


def parse_args():
    parser = argparse.ArgumentParser(description="Ismételt kiértékelések összesítése")
    parser.add_argument("files", nargs="+", help="eredményfájlok (glob minta is lehet)")
    parser.add_argument("--output", help="összesítés mentése JSON-be")
    return parser.parse_args()


def main():
    args = parse_args()

    # Windows shells do not expand globs, so expand them here.
    paths = sorted({p for pattern in args.files for p in (glob.glob(pattern) or [pattern])})
    runs = load_runs(paths)
    if not runs:
        raise SystemExit("Nincs kiértékelési eredmény a megadott fájlok között.")

    summary = summarize(runs)
    print_summary(summary)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as file:
            json.dump(summary, file, ensure_ascii=False, indent=2)
        print(f"\nÖsszesítés mentve: {args.output}")


if __name__ == "__main__":
    main()
