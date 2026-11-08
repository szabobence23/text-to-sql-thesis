"""
Compare setups measured with run_batch.py: accuracy per dataset and
language, a 95% confidence interval, and a paired exact McNemar test per
question against a reference setup.

    python src/evaluation/compare.py final-m1-baseline final-m2-rag \
        --labels "Alap" "+ RAG" --reference final-m1-baseline --markdown docs/results.md

Each argument is a batch run name (the newest results/*_batch_<name>.json)
or a batch file path. One repeat per setup is enough: repeated runs were
practically identical, the uncertainty comes from the number of questions
(see CLAUDE.md), so questions are paired across setups instead.
"""

import argparse
import glob
import math
import os
import sys
from collections import defaultdict

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(SRC_DIR)

import json

from evaluation.evaluator import DEFAULT_OUTPUT_DIR


DATASET_ORDER = ["olist", "f1", "adventureworks", "sales"]
DATASET_LABELS = {"olist": "Olist", "f1": "F1", "adventureworks": "AdventureWorks", "sales": "sales"}
METRICS = {"relaxed": "relaxed_match", "strict": "strict_match"}
# Runs compared question by question must agree on these.
MUST_MATCH = ["test_cases_sha256", "model_digest", "prompt_sha256"]


def find_batch(name_or_path, results_dir):
    if os.path.exists(name_or_path):
        return name_or_path
    matches = sorted(glob.glob(os.path.join(results_dir, f"*_batch_{name_or_path}.json")))
    if not matches:
        sys.exit(f"Nincs batch-fájl ehhez: {name_or_path}")
    return matches[-1]


def load_setup(name_or_path, results_dir):
    """{"name", "args", "git", "runs": [evaluator results]} of one batch."""
    path = find_batch(name_or_path, results_dir)
    with open(path, encoding="utf-8") as file:
        batch = json.load(file)["batch"]
    runs = []
    for name in batch["files"]:
        with open(os.path.join(os.path.dirname(path), name), encoding="utf-8") as file:
            runs.append(json.load(file))
    return {"name": batch["run_name"], "args": batch["evaluator_args"], "git": batch["git"], "runs": runs}


def outcomes(setup, metric):
    """{(dataset, language, question id): correct}"""
    result = {}
    for run in setup["runs"]:
        dataset = run["run"]["pipeline"]["dataset"]
        language = run["run"]["test_cases_language"]
        for question in run["results"]:
            result[(dataset, language, question["id"])] = bool(question[METRICS[metric]])
    return result


def wilson(correct, total, z=1.96):
    """95% Wilson score interval of a proportion, as (low, high)."""
    if total == 0:
        return 0.0, 0.0
    p = correct / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return centre - half, centre + half


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p: b, c = questions only one setup got right."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def format_p(p):
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def compare(setups, labels, reference, metric):
    """Rows of the comparison table and warnings, as plain data."""
    ref = outcomes(setups[reference], metric)
    rows = []
    for setup, label in zip(setups, labels):
        result = outcomes(setup, metric)
        if result.keys() != ref.keys():
            sys.exit(f"{setup['name']}: nem ugyanazok a kérdések, mint a viszonyítási alapban")

        by_dataset = defaultdict(list)
        by_language = defaultdict(list)
        for (dataset, language, _), correct in result.items():
            by_dataset[dataset].append(correct)
            by_language[language].append(correct)

        better = sum(result[k] and not ref[k] for k in ref)  # right only here
        worse = sum(ref[k] and not result[k] for k in ref)  # right only in the reference
        total = len(result)
        correct = sum(result.values())
        rows.append({
            "label": label,
            "name": setup["name"],
            "args": " ".join(setup["args"]) or "(alap)",
            "datasets": {d: (sum(v), len(v)) for d, v in by_dataset.items()},
            "languages": {l: (sum(v), len(v)) for l, v in by_language.items()},
            "correct": correct,
            "total": total,
            "ci": wilson(correct, total),
            "better": better,
            "worse": worse,
            "p": mcnemar_exact(better, worse),
        })

    warnings = []
    commits = {(s["git"]["commit"], s["git"]["dirty"]) for s in setups}
    if len(commits) > 1:
        warnings.append(f"A setupok különböző commitokon futottak: {sorted(commits)}")
    if any(dirty for _, dirty in commits):
        warnings.append("Legalább egy setup commitolatlan kóddal futott (dirty).")
    for key in MUST_MATCH:
        values = {run["run"].get(key) for s in setups for run in s["runs"]
                  if run["run"]["test_cases_language"] == "hu" and run["run"]["pipeline"]["dataset"] == "olist"}
        if len(values) > 1:
            warnings.append(f"Eltérő {key} a setupok között (Olist, hu).")
    return rows, warnings


def markdown(rows, labels, reference, metric, warnings, setups):
    datasets = [d for d in DATASET_ORDER if d in rows[0]["datasets"]]
    languages = sorted(rows[0]["languages"], key=lambda l: (l != "hu", l))  # hu first
    head = ["Beállítás", *(DATASET_LABELS[d] for d in datasets), *languages, "Összesen", "95% CI",
            f"Δ vs. {labels[reference]}", "+/−", "McNemar p"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for i, row in enumerate(rows):
        delta = row["correct"] - rows[reference]["correct"]
        cells = [
            row["label"],
            *(f"{row['datasets'][d][0]}/{row['datasets'][d][1]}" for d in datasets),
            *(f"{row['languages'][l][0]}/{row['languages'][l][1]}" for l in languages),
            f"**{row['correct']}/{row['total']}** ({row['correct'] / row['total']:.0%})",
            f"{row['ci'][0]:.0%}–{row['ci'][1]:.0%}",
            "—" if i == reference else f"{delta:+d}",
            "—" if i == reference else f"+{row['better']} / −{row['worse']}",
            "—" if i == reference else format_p(row["p"]),
        ]
        lines.append("| " + " | ".join(cells) + " |")

    lines += ["", f"Mérőszám: {metric} EX. „+/−”: kérdések, amelyeket csak ez a beállítás, ill. csak a viszonyítási alap oldott meg helyesen (ezekből a McNemar-próba).", ""]
    lines += ["| Beállítás | Evaluator-kapcsolók | Batch |", "|---|---|---|"]
    lines += [f"| {r['label']} | `{r['args']}` | `{r['name']}` |" for r in rows]
    lines += ["", f"Commit: `{setups[0]['git']['commit'][:7]}`", ""]
    if warnings:
        lines += ["**Figyelmeztetések:**", *(f"- {w}" for w in warnings), ""]
    return "\n".join(lines)


def parse_args():
    parser = argparse.ArgumentParser(description="Beállítások összevetése kérdésenként párosítva (McNemar)")
    parser.add_argument("setups", nargs="+", help="batch-nevek vagy batch-fájlok")
    parser.add_argument("--labels", nargs="+", help="megjelenített nevek, a setupok sorrendjében")
    parser.add_argument("--reference", default=None, help="a viszonyítási alap batch-neve (alapértelmezés: az első)")
    parser.add_argument("--metric", choices=sorted(METRICS), default="relaxed")
    parser.add_argument("--results-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--markdown", help="a táblázat mentése ebbe a markdown-fájlba")
    return parser.parse_args()


def main():
    args = parse_args()
    setups = [load_setup(name, args.results_dir) for name in args.setups]
    labels = args.labels or [s["name"] for s in setups]
    if len(labels) != len(setups):
        sys.exit("A --labels elemszáma nem egyezik a setupokéval.")
    names = [s["name"] for s in setups]
    reference = names.index(args.reference) if args.reference else 0

    rows, warnings = compare(setups, labels, reference, args.metric)
    text = markdown(rows, labels, reference, args.metric, warnings, setups)
    print(text)

    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as file:
            file.write(text + "\n")
        print(f"\nMentve: {args.markdown}")


if __name__ == "__main__":
    main()
