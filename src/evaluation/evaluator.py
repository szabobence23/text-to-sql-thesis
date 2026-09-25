import json
import os
import sys

# src könyvtár elérhetővé tétele
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection, execute_query
from schema import get_schema
from llm import generate_sql


def normalize_result(result):
    """
    PostgreSQL eredmény -> JSON-kompatibilis forma.
    """
    return [list(row) for row in result]


def evaluate_test_case(conn, schema, test_case):
    question = test_case["question"]
    ground_truth_sql = test_case["ground_truth_sql"]

    expected_result = execute_query(
        conn,
        ground_truth_sql
    )

    expected_result = normalize_result(expected_result)

    print("=" * 80)
    print(f"TESZT {test_case['id']}")
    print("=" * 80)

    print("\nKérdés:")
    print(question)

    # LLM SQL generálás
    generated_sql = generate_sql(question, schema)

    print("\nGenerált SQL:")
    print(generated_sql)

    # SQL végrehajtása
    try:
        result = execute_query(conn, generated_sql)
        result = normalize_result(result)

        execution_success = True

        print("\nAdatbázis eredménye:")
        for row in result:
            print(row)

    except Exception as e:
        conn.rollback()

        result = None
        execution_success = False

        print("\nSQL HIBA:")
        print(e)

    # Execution accuracy
    execution_accuracy = (
        execution_success and result == expected_result
    )

    print("\nHelyes eredmény?")
    print("YES" if execution_accuracy else "NO")

    return {
        "id": test_case["id"],
        "question": question,
        "category": test_case["category"],
        "difficulty": test_case["difficulty"],
        "ground_truth_sql": test_case["ground_truth_sql"],
        "expected_result": expected_result,
        "generated_sql": generated_sql,
        "generated_result": result,
        "execution_success": execution_success,
        "execution_accuracy": execution_accuracy
    }


def main():

    # Test case-ok betöltése
    with open(
        "src/evaluation/test_cases.json",
        "r",
        encoding="utf-8"
    ) as file:
        test_cases = json.load(file)

    conn = get_connection()

    try:

        # Schema egyszeri lekérése
        schema = get_schema(conn)

        print("Olist adatbázis séma betöltve.")

        results = []

        for test_case in test_cases:
            result = evaluate_test_case(
                conn,
                schema,
                test_case
            )

            results.append(result)

        # Statisztikák
        total = len(results)

        successful_executions = sum(
            r["execution_success"]
            for r in results
        )

        correct_results = sum(
            r["execution_accuracy"]
            for r in results
        )

        execution_success_rate = (
            successful_executions / total
            if total > 0 else 0
        )

        execution_accuracy = (
            correct_results / total
            if total > 0 else 0
        )

        print("\n" + "=" * 80)
        print("EVALUATION SUMMARY")
        print("=" * 80)

        print(f"\nTesztkérdések: {total}")
        print(f"SQL execution success: {successful_executions}/{total} "
              f"({execution_success_rate:.1%})")
        print(f"Execution accuracy: {correct_results}/{total} "
              f"({execution_accuracy:.1%})")

        # Eredmények mentése
        output = {
            "model": "qwen2.5-coder:7b",
            "database": "olist_db",
            "total_questions": total,
            "sql_execution_success": successful_executions,
            "sql_execution_success_rate": execution_success_rate,
            "correct_results": correct_results,
            "execution_accuracy": execution_accuracy,
            "results": results
        }

        os.makedirs(
            "src/evaluation/results",
            exist_ok=True
        )

        with open(
            "src/evaluation/results/qwen_baseline.json",
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                output,
                file,
                ensure_ascii=False,
                indent=2,
                default=str
            )

        print("\nEredmények mentve:")
        print("src/evaluation/results/qwen_baseline.json")

    finally:
        conn.close()


if __name__ == "__main__":
    main()