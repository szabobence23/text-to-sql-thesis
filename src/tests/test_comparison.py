import datetime
from decimal import Decimal

import pytest

from evaluation.comparison import (
    is_order_sensitive,
    match_any,
    normalize_rows,
    relaxed_match,
    strict_match,
)


@pytest.mark.parametrize(
    "sql, expected",
    [
        ("SELECT COUNT(*) FROM orders;", False),
        ("SELECT a FROM t ORDER BY a DESC LIMIT 5;", True),
        # ORDER BY only inside a subquery does not order the result.
        ("SELECT * FROM (SELECT a FROM t ORDER BY a) s;", False),
        ("WITH c AS (SELECT a FROM t) SELECT a FROM c ORDER BY a;", True),
    ],
)
def test_is_order_sensitive(sql, expected):
    assert is_order_sensitive(sql) == expected


def test_normalize_rounds_decimals_and_floats_alike():
    rows = normalize_rows([(Decimal("120.6537390146471372"),), (120.65373901,)])

    assert rows[0] == rows[1]


def test_durations_compare_as_days():
    # The model's interval answer and the ground truth's number of days
    # (Olist question 31: average delivery time).
    interval = datetime.timedelta(days=12, hours=13, minutes=24, seconds=31.879068)
    days = Decimal("12.55870230403205249294")

    assert normalize_rows([(interval,)]) == normalize_rows([(days,)])
    assert normalize_rows([(interval,)]) == [(12.5587,)]


def test_strict_ignores_row_order_when_unordered():
    assert strict_match([(1,), (2,)], [(2,), (1,)], ordered=False)
    assert not strict_match([(1,), (2,)], [(2,), (1,)], ordered=True)


def test_strict_requires_same_columns():
    assert not strict_match([("SP",)], [("SP", 41746)], ordered=True)


def test_relaxed_accepts_extra_columns():
    # Test case 4: the model also returned the customer count.
    assert relaxed_match([("SP",)], [("SP", 41746)], ordered=True)


def test_relaxed_accepts_permuted_columns():
    expected = [("a", 1), ("b", 2)]
    generated = [(1, "x", "a"), (2, "y", "b")]

    assert relaxed_match(expected, generated, ordered=True)


def test_relaxed_requires_same_row_count():
    assert not relaxed_match([("a",)], [("a",), ("b",)], ordered=False)


def test_relaxed_respects_order_when_ordered():
    expected = [("a", 2), ("b", 1)]
    generated = [("b", 1), ("a", 2)]

    assert not relaxed_match(expected, generated, ordered=True)
    assert relaxed_match(expected, generated, ordered=False)


def test_relaxed_checks_row_pairing_not_only_columns():
    # Each column matches as a multiset, but the rows pair differently.
    expected = [("a", 1), ("b", 2)]
    generated = [("a", 2), ("b", 1)]

    assert not relaxed_match(expected, generated, ordered=False)


def test_relaxed_empty_results_match():
    assert relaxed_match([], [], ordered=False)


def test_match_any_prefers_the_ground_truth_then_alternatives():
    english = [("bed_bath_table", 11115)]
    portuguese = [("cama_mesa_banho", 11115)]
    accepted = [english, portuguese]

    assert match_any(accepted, [("bed_bath_table", 11115)], [True, True]) == (True, True, 0)
    assert match_any(accepted, [("cama_mesa_banho", 11115)], [True, True]) == (True, True, 1)
    # Extra columns: relaxed match only.
    assert match_any(accepted, [("cama_mesa_banho", 11115, 7)], [True, True]) == (False, True, 1)
    assert match_any(accepted, [("moveis_decoracao", 8334)], [True, True]) == (False, False, None)
