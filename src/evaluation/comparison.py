"""
Result comparison for execution accuracy (EX).

strict:  same rows with the same columns in the same column order.
relaxed: every ground-truth column appears somewhere in the generated
         result (extra columns allowed), with the same rows.

Row order only matters when the ground-truth query has a top-level
ORDER BY (Spider convention); otherwise rows are compared as multisets.

A test case can accept several answers (alternative_sql next to the
ground truth); match_any takes the first one that matches.

Numbers are rounded to FLOAT_DIGITS decimals. A duration (PostgreSQL
interval) becomes a number of days, so '12 days 13:24:31' and the same
duration computed as 12.5587 days count as the same answer.
"""

import datetime
from collections import Counter
from decimal import Decimal

import sqlglot


FLOAT_DIGITS = 4


def normalize_value(value):
    if isinstance(value, (Decimal, float)):
        return round(float(value), FLOAT_DIGITS)

    if isinstance(value, datetime.timedelta):
        return round(value.total_seconds() / 86400, FLOAT_DIGITS)

    if isinstance(value, (datetime.date, datetime.datetime, datetime.time)):
        return value.isoformat()

    return value


def normalize_rows(rows):
    return [tuple(normalize_value(v) for v in row) for row in rows]


def is_order_sensitive(ground_truth_sql: str) -> bool:
    tree = sqlglot.parse_one(ground_truth_sql, read="postgres")
    return tree.args.get("order") is not None


def _same_rows(expected, generated, ordered):
    if ordered:
        return expected == generated

    return Counter(expected) == Counter(generated)


def strict_match(expected, generated, ordered) -> bool:
    return _same_rows(expected, generated, ordered)


def relaxed_match(expected, generated, ordered) -> bool:
    if len(expected) != len(generated):
        return False

    if not expected:
        return True

    expected_width = len(expected[0])
    generated_width = len(generated[0])

    if generated_width < expected_width:
        return False

    def column(rows, i):
        values = [row[i] for row in rows]
        return values if ordered else Counter(values)

    # Candidate generated columns for each expected column, by value.
    candidates = [
        [
            j for j in range(generated_width)
            if column(generated, j) == column(expected, i)
        ]
        for i in range(expected_width)
    ]

    # Columns can match individually but pair up rows differently,
    # so every assignment is checked on whole rows.
    def assign(i, used):
        if i == expected_width:
            projected = [tuple(row[j] for j in used) for row in generated]
            return _same_rows(expected, projected, ordered)

        return any(
            assign(i + 1, used + [j])
            for j in candidates[i]
            if j not in used
        )

    return assign(0, [])


def match_any(expected_results, generated, ordered_flags):
    """
    Compare against every accepted answer of a test case (the ground
    truth first, then its alternatives, e.g. a category named in
    Portuguese instead of English).

    Returns (strict, relaxed, index): the matches against the first
    answer that matches relaxed, with its index; (False, False, None)
    if none does.
    """
    for index, (expected, ordered) in enumerate(zip(expected_results, ordered_flags)):
        if relaxed_match(expected, generated, ordered):
            return strict_match(expected, generated, ordered), True, index
    return False, False, None
