"""Offline tests of the fine-tuning data scripts in finetune/ (no database, no LLM)."""

import datetime
from decimal import Decimal

import pytest

from build_self_distill import answer_from_response, candidates, choose
from build_sft_data import answer_text, pick_examples, same_sql
from eval_valid import score, summary
from import_bird_train import EXCLUDED, FLOAT_TYPE, decide_type, pg_name, sqlite_float_text
from transpile_gold import as_set, normalize, translate


def counts(integer=0, real=0, text=0, blob=0):
    return {"integer": integer, "real": real, "text": text, "blob": blob}


def test_adventureworks_copy_is_never_imported():
    assert "works_cycles" in EXCLUDED


def test_plain_names_are_lowercased_others_kept():
    assert pg_name("customerNumber") == "customernumber"
    assert pg_name("Order Date") == "Order Date"
    assert pg_name("+/-") == "+/-"


@pytest.mark.parametrize("declared, stored, expected", [
    ("INTEGER", counts(integer=5), "bigint"),
    ("INTEGER", counts(integer=5, real=1), FLOAT_TYPE),
    ("INTEGER", counts(integer=5, text=1), "text"),
    ("REAL", counts(real=5, integer=2), FLOAT_TYPE),
    ("TEXT", counts(text=5), "text"),
    ("DATE", counts(text=5), "date?"),
    ("DATETIME", counts(text=5), "timestamp?"),
    ("DATE", counts(integer=5), "bigint"),
    ("BLOB", counts(), "bytea"),
    ("BLOB", counts(text=3), "text"),
])
def test_column_types_follow_the_stored_values(declared, stored, expected):
    assert decide_type(declared, stored)[0] == expected


def test_real_is_eight_bytes():
    # A 4-byte real column makes `rental_rate = 2.99` find nothing.
    assert FLOAT_TYPE == "double precision"


def test_sqlite_float_text():
    assert sqlite_float_text(100.0) == "100.0"
    assert sqlite_float_text(2.5) == "2.5"


NAMES = {"order date": "Order Date", "customers": "customers", "name": "name", "rate": "rate"}


def test_clean_translation_is_plain_postgres():
    sql = translate("SELECT CAST(SUM(rate) AS REAL) / COUNT(*) FROM Customers ORDER BY name DESC LIMIT 2, 3",
                    NAMES, "clean")
    assert sql == "SELECT CAST(SUM(rate) AS REAL) / COUNT(*) FROM customers ORDER BY name DESC LIMIT 3 OFFSET 2"


def test_faithful_translation_keeps_sqlite_semantics():
    sql = translate("SELECT CAST(rate AS REAL) FROM customers WHERE name LIKE 'a%' ORDER BY rate DESC",
                    NAMES, "faithful")
    assert "ILIKE" in sql and "NULLS LAST" in sql and "DOUBLE PRECISION" in sql


def test_faithful_translation_never_puts_nulls_first():
    # SQLite's ascending NULLS FIRST makes a NULL row "the shortest": a gold defect.
    sql = translate("SELECT name FROM customers ORDER BY rate LIMIT 1", NAMES, "faithful")
    assert "NULLS FIRST" not in sql


def test_names_and_double_quoted_strings():
    sql = translate('SELECT `ORDER DATE` FROM customers WHERE name = "John"', NAMES, "clean")
    # Non-plain names match the stored name whatever the case; a quoted
    # word that names nothing is a string, as SQLite reads it.
    assert sql == "SELECT \"Order Date\" FROM customers WHERE name = 'John'"


def test_quoted_alias_is_not_turned_into_a_string():
    sql = translate('SELECT name AS "Total" FROM customers ORDER BY "Total"', NAMES, "clean")
    assert "'Total'" not in sql


def test_normalize_matches_sqlite_and_postgres_values():
    assert normalize(Decimal("3.00")) == normalize(3) == 3
    assert normalize(True) == 1
    assert normalize(2.990000009) == normalize(2.99)
    assert normalize(datetime.datetime(2005, 5, 25, 11, 30, 37)) == normalize("2005-05-25 11:30:37.0")
    assert normalize(datetime.date(2013, 1, 3)) == "2013-01-03"
    assert normalize("12") == 12
    assert as_set([(1, "a"), (1, "a")]) == {(1, "a")}


def test_answer_is_a_fenced_pretty_query():
    text = answer_text("SELECT a, COUNT(*) FROM t WHERE b = 1 GROUP BY a")
    assert text.startswith("```sql\nSELECT\n") and text.endswith(";\n```")


def test_examples_never_give_the_answer_away():
    items = [{"id": i, "sql": sql} for i, sql in enumerate(
        ["SELECT 1", "select   1", "SELECT 2", "SELECT 3", "SELECT 4"])]
    vectors = [[1.0, 0.0], [1.0, 0.0], [0.95, 0.31], [0.6, 0.8], [0.0, 1.0]]
    picked = pick_examples(0, items, vectors, 3)
    ids = [x["id"] for x, _ in picked]
    # Not itself, not the same SQL (#1), not too similar (#2: 0.95 >= 0.9).
    assert ids == [3, 4]
    assert same_sql("SELECT 1", "select   1")


def test_valid_eval_scores_like_the_evaluator():
    expected = [(1, "a"), (2, "b")]
    # Extra column: relaxed only; another row order: still a match (no ORDER BY).
    assert score(expected, [(2, "b", 0), (1, "a", 0)], ordered=False) == {"set": False, "relaxed": True, "strict": False}
    assert score(expected, [(2, "b"), (1, "a")], ordered=False) == {"set": True, "relaxed": True, "strict": True}
    assert score(expected, None, ordered=False) == {"set": False, "relaxed": False, "strict": False}


def test_valid_eval_summary_groups():
    def row(db, evidence, examples, ok):
        return {"db_id": db, "evidence_shown": evidence, "examples": examples, "set": ok, "relaxed": ok, "strict": ok}
    s = summary([row("a", True, 0, True), row("a", False, 3, False), row("b", False, 0, True)])
    assert s["all"] == {"set": 2, "relaxed": 2, "strict": 2, "total": 3}
    assert s["evidence"]["total"] == 1 and s["examples"]["set"] == 0
    assert s["by_database"]["b"] == {"set": 1, "relaxed": 1, "strict": 1, "total": 1}


def test_self_distilled_answer_is_the_models_own_block():
    own = "```sql\nSELECT name FROM t;\n```"
    assert answer_from_response(own + "\n") == own
    # Text around the block is dropped, the SQL is kept as written.
    assert answer_from_response("Here:\n```sql\nSELECT  a\nFROM t\n```\nDone.") == "```sql\nSELECT  a\nFROM t\n```"
    assert answer_from_response("SELECT 1") == "```sql\nSELECT 1\n```"


def test_candidates_greedy_first_and_each_sql_once():
    generation = {"greedy": "```sql\nSELECT 1\n```",
                  "samples": ["```sql\nselect   1\n```", "```sql\nSELECT 2\n```", ""]}
    assert [source for source, _ in candidates(generation)] == ["greedy", "sample1"]


def test_first_correct_candidate_is_kept():
    generation = {"greedy": "```sql\nSELECT 1\n```",
                  "samples": ["```sql\nSELECT 2\n```", "```sql\nSELECT 3\n```"]}
    outcomes = {"SELECT 1": "wrong", "SELECT 2": "relaxed", "SELECT 3": "set"}
    source, text, tried = choose(generation, outcomes.get)
    assert source == "sample0" and "SELECT 2" in text
    assert tried == [("greedy", "wrong"), ("sample0", "relaxed")]
    assert choose({"greedy": "```sql\nSELECT 1\n```", "samples": []}, outcomes.get)[0] is None
