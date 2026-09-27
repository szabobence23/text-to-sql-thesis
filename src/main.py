import argparse

from dataset_loader import DEFAULT_DATASET
from pipeline import PipelineConfig, load_schema, open_connection, run_pipeline


DEFAULT_QUESTION = "Melyik termékkategóriából adták el a legtöbb terméket?"


def parse_args():
    parser = argparse.ArgumentParser(description="Text-to-SQL demó")
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    return parser.parse_args()


def main():
    args = parse_args()

    config = PipelineConfig(dataset=args.dataset, max_correction_rounds=2)
    conn = open_connection(config)

    try:
        schema = load_schema(conn, config)

        question = args.question

        print("Kérdés:")
        print(question)

        result = run_pipeline(conn, question, schema, config)

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

    finally:
        conn.close()


if __name__ == "__main__":
    main()
