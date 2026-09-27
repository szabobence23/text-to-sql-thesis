from decimal import Decimal

import pytest

from evaluation.comparison import (
    is_order_sensitive,
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
