import argparse

from dataset_loader import DEFAULT_DATASET
from pipeline import (
    PipelineConfig,
    load_schema,
    make_schema_retriever,
    open_connection,
    run_pipeline,
)
from retrieval import RETRIEVAL_METHODS
from sql_tables import format_tables


DEFAULT_QUESTION = "Melyik termékkategóriából adták el a legtöbb terméket?"


def parse_args():
    parser = argparse.ArgumentParser(description="Text-to-SQL demó")
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument(
        "--no-answer",
        action="store_true",
        help="természetes nyelvű válasz nélkül, csak az SQL és a sorok",
    )
    parser.add_argument(
        "--schema-retrieval",
        default="full",
        choices=["full", *RETRIEVAL_METHODS],
        help="full = a teljes séma; bm25 / dense / hybrid = csak a kereső által választott táblák",
    )
    parser.add_argument("--column-values", action="store_true", help="a kategória-oszlopok értékei is a sémában")
    parser.add_argument("--retrieval-k", type=int, default=5, help="a keresés után megtartott táblák száma")
    parser.add_argument(
        "--table-selection",
        action="store_true",
        help="az LLM kiválasztja a jelöltek közül a szükséges táblákat (javasolt: --retrieval-k 10)",
    )
    parser.add_argument("--translate-for-retrieval", action="store_true", help="keresés előtt angolra fordítja a kérdést")
    return parser.parse_args()


def main():
    args = parse_args()

    config = PipelineConfig(
        dataset=args.dataset,
        max_correction_rounds=2,
        natural_language_answer=not args.no_answer,
        schema_retrieval=args.schema_retrieval,
        translate_for_retrieval=args.translate_for_retrieval,
        column_values=args.column_values,
        retrieval_k=args.retrieval_k,
        table_selection=args.table_selection,
    )
    conn = open_connection(config)

    try:
        schema = load_schema(conn, config)
        retriever = make_schema_retriever(conn, config)

        question = args.question

        print("Kérdés:")
        print(question)

        result = run_pipeline(conn, question, schema, config, retriever)

        if result.schema_tables is not None:
            if result.translation:
                print(f"\nKeresés fordítással: {result.retrieval_query}")
            if result.candidate_tables is not None:
                print(f"\nJelölt táblák ({len(result.candidate_tables)}):")
                print(", ".join(format_tables(result.candidate_tables)))
            print(f"\nKiválasztott táblák ({len(result.schema_tables)}):")
            print(", ".join(format_tables(result.schema_tables)))

        for i, attempt in enumerate(result.attempts[:-1], start=1):
            print(f"\n{i}. próbálkozás (hibás):")
            print(attempt.sql)
            print(f"Hiba: {attempt.error}")

        if result.correction_rounds:
            print(f"\nGenerált SQL ({result.correction_rounds}. javítás után):")
        else:
            print("\nGenerált SQL:")
        print(result.sql)

        if not result.is_valid:
            print("\nSQL validációs hiba:")
            print(result.validation_error)
            return

        if not result.executed:
            print("\nSQL végrehajtási hiba:")
            print(result.execution_error)
            return

        print("\nAdatbázis eredménye:")

        if result.rows:
            for row in result.rows:
                print(row)
        else:
            print("(Nincs eredmény)")

        if result.answer:
            print("\nVálasz:")
            print(result.answer.text)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
