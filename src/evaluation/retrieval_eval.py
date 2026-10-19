"""
Schema retrieval measured on its own, without the LLM.

    python src/evaluation/retrieval_eval.py --run-name bm25
    python src/evaluation/retrieval_eval.py --run-name bm25-desc --descriptions

For every test question the retriever ranks the tables; the tables the
ground truth reads (sql_tables.tables_in_sql) are what it should find.
Per top-k, with and without foreign-key expansion, it reports:
- complete: every needed table was found (otherwise the model cannot
  write a correct query, whatever it does);
- recall: the share of needed tables found;
- shown: how many tables the prompt would list.
It also reports the rank of the last needed table, i.e. how many tables
the prompt would need for the question to be answerable.

Runs in seconds, so retrieval variants can be compared before spending
LLM runs on the promising ones.
"""

import argparse
import datetime
import json
import os
import statistics
import sys

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(SRC_DIR)

from dataset_loader import available_datasets, load_dataset
from evaluation.evaluator import DEFAULT_OUTPUT_DIR, git_info, sha256
from pipeline import PipelineConfig, open_connection
from retrieval import BM25Retriever, foreign_key_graph, load_table_docs, select_tables
from sql_tables import format_tables, table_recall, tables_in_sql


DEFAULT_DATASETS = ["olist", "f1", "adventureworks"]
DEFAULT_KS = [1, 2, 3, 5, 8, 10]


def parse_args():
    parser = argparse.ArgumentParser(description="Sémakeresés mérése LLM nélkül (recall@k)")
    parser.add_argument("--datasets", nargs="+", default=DEFAULT_DATASETS, choices=available_datasets())
    parser.add_argument("--languages", nargs="+", default=["hu", "en"])
    parser.add_argument("--k", nargs="+", type=int, default=DEFAULT_KS, help="hány táblát adjon vissza a kereső")
    parser.add_argument("--ngram", type=int, default=3, help="karakter n-gram hossza; 0 = egész szavak")
    parser.add_argument("--descriptions", action="store_true", help="a tábla- és oszlopleírások is kereshetők")
    parser.add_argument("--max-hops", type=int, default=2, help="idegen kulcs menti bővítés legnagyobb úthossza")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-name", default="", help="rövid név a fájlnévbe")
    return parser.parse_args()


def evaluate(cases, retriever, graph, ks, max_hops):
    questions = []
    for case in cases:
        gold = tables_in_sql(case["ground_truth_sql"])
        ranking = retriever.rank(case["question"])
        order = [key for key, _ in ranking]
        ranks = {key: order.index(key) + 1 for key in gold if key in order}

        per_k = {}
        for k in ks:
            for expansion in (False, True):
                shown = select_tables(ranking, k, graph, expansion, max_hops)
                per_k[f"{k}{'+fk' if expansion else ''}"] = {
                    "recall": table_recall(gold, shown),
                    "complete": gold <= set(shown),
                    "shown": len(shown),
                }

        questions.append({
            "id": case["id"],
            "question": case["question"],
            "gold_tables": format_tables(gold),
            "gold_ranks": {format_tables([k])[0]: r for k, r in sorted(ranks.items())},
            # Rank of the last needed table: the k at which the question
            # becomes answerable without expansion.
            "rank_needed": max(ranks.values()) if len(ranks) == len(gold) else None,
            "top10": format_tables_ordered(order[:10]),
            "per_k": per_k,
        })
    return questions


def format_tables_ordered(keys):
    return [format_tables([k])[0] for k in keys]


def summarize(questions, ks):
    summary = {}
    for k in ks:
        for suffix in ("", "+fk"):
            key = f"{k}{suffix}"
            rows = [q["per_k"][key] for q in questions]
            summary[key] = {
                "complete": statistics.mean(r["complete"] for r in rows),
                "recall": statistics.mean(r["recall"] for r in rows),
                "shown": statistics.mean(r["shown"] for r in rows),
            }
    needed = [q["rank_needed"] for q in questions if q["rank_needed"] is not None]
    summary["rank_needed_median"] = statistics.median(needed) if needed else None
    summary["rank_needed_mean"] = statistics.mean(needed) if needed else None
    return summary


def main():
    args = parse_args()
    started_at = datetime.datetime.now()
    ks = sorted(set(args.k))

    print(
        f"Kereső: BM25, {'egész szavak' if args.ngram <= 0 else f'karakter {args.ngram}-gram'}, "
        f"leírások: {'igen' if args.descriptions else 'nem'}, bővítés: legfeljebb {args.max_hops} lépés"
    )
    header = "  ".join(f"k={k:<3}" for k in ks)
    print(f"\nTeljes találat (minden szükséges tábla az első k között):")
    print(f"{'Dataset':15} {'Nyelv':5} {'Táblák':>6}  {'Bővítés':8} {header}   Átl. tábla k={ks[-1]}  Medián rang")

    output = {
        "run": {
            "started_at": started_at.isoformat(timespec="seconds"),
            "git": git_info(),
            "retriever": "bm25",
            "ngram": args.ngram,
            "descriptions": args.descriptions,
            "max_hops": args.max_hops,
            "ks": ks,
        },
        "results": [],
    }

    for name in args.datasets:
        dataset = load_dataset(name)
        conn = open_connection(PipelineConfig(dataset=name))
        try:
            docs = load_table_docs(conn, dataset.schemas)
            graph = foreign_key_graph(conn, dataset.schemas)
        finally:
            conn.close()

        retriever = BM25Retriever(docs, ngram=args.ngram, with_descriptions=args.descriptions)

        for language in args.languages:
            if language not in dataset.languages:
                continue
            with open(dataset.test_cases_path(language), encoding="utf-8") as file:
                cases_text = file.read()
            cases = json.loads(cases_text)

            questions = evaluate(cases, retriever, graph, ks, args.max_hops)
            summary = summarize(questions, ks)

            for suffix, label in (("", "nincs"), ("+fk", "FK")):
                cells = "  ".join(f"{summary[f'{k}{suffix}']['complete']:5.0%}" for k in ks)
                shown = summary[f"{ks[-1]}{suffix}"]["shown"]
                rank = summary["rank_needed_median"] if not suffix else ""
                print(f"{name:15} {language:5} {len(docs):>6}  {label:8} {cells}   {shown:10.1f}  {rank!s:>11}")

            output["results"].append({
                "dataset": name,
                "language": language,
                "tables": len(docs),
                "test_cases_sha256": sha256(cases_text),
                "summary": summary,
                "questions": questions,
            })

    stamp = started_at.strftime("%Y%m%d-%H%M%S")
    name = f"{stamp}_retrieval_bm25" + (f"_{args.run_name}" if args.run_name else "")
    path = os.path.join(args.output_dir, f"{name}.json")
    os.makedirs(args.output_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    print(f"\nEredmények mentve:\n{path}")


if __name__ == "__main__":
    main()
