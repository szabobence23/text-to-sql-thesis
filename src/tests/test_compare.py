import pytest

from evaluation.compare import DATASET_ORDER, format_p, mcnemar_exact, ordered, wilson


def test_mcnemar_exact():
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(5, 5) == 1.0
    # 28 vs 7 discordant questions: sum of C(35, i) for i <= 7, times 2, over 2^35.
    assert mcnemar_exact(28, 7) == pytest.approx(0.000508, abs=1e-6)
    assert mcnemar_exact(7, 28) == mcnemar_exact(28, 7)
    assert mcnemar_exact(10, 0) == pytest.approx(2 / 2 ** 10)


def test_wilson():
    low, high = wilson(235, 300)
    assert low == pytest.approx(0.733, abs=0.001)
    assert high == pytest.approx(0.826, abs=0.001)
    assert wilson(0, 0) == (0.0, 0.0)
    low, high = wilson(50, 50)
    assert high == pytest.approx(1.0) and low < 1.0


def test_format_p():
    assert format_p(0.000508) == "< 0.001"
    assert format_p(0.0768) == "0.077"
    assert format_p(1.0) == "1.000"


def test_known_names_keep_their_order_others_follow():
    assert ordered({"bird_financial", "f1", "olist", "bird_card_games"}, DATASET_ORDER) == [
        "olist", "f1", "bird_card_games", "bird_financial",
    ]
