import pytest

from evaluation.report import summarize


def fake_run(dataset, language, relaxed_by_id, prompt="p1", correction=0):
    results = [
        {"id": i, "difficulty": "easy" if i == 1 else "hard", "relaxed_match": ok}
        for i, ok in relaxed_by_id.items()
    ]
    n = len(results)
    hits = sum(relaxed_by_id.values())
    rate = {"count": hits, "total": n, "rate": hits / n}
    return {
        "_path": f"{dataset}-{language}.json",
        "run": {
            "pipeline": {
                "dataset": dataset,
                "max_correction_rounds": correction,
                "schema_hints": True,
                "llm": {"model": "m", "temperature": 0.0},
            },
            "test_cases_language": language,
            "prompt_sha256": prompt,
            "test_cases_sha256": "t",
            "schema_sha256": "s",
            "model_digest": "d",
            "git": {"dirty": False},
        },
        "summary": {
            "total_questions": n,
            "valid_sql": rate,
            "strict_ex": rate,
            "relaxed_ex": rate,
            "mean_generation_s": 1.0,
            "mean_prompt_tokens": 10,
        },
        "results": results,
    }


def test_repeats_are_grouped_with_mean_and_std():
    runs = [
        fake_run("olist", "hu", {1: True, 2: True}),
        fake_run("olist", "hu", {1: True, 2: False}),
    ]

    [group] = summarize(runs)

    assert group["runs"] == 2
    assert group["rates"]["relaxed_ex"]["mean"] == pytest.approx(0.75)
    assert group["rates"]["relaxed_ex"]["std"] == pytest.approx(0.3536, abs=1e-4)
    # Question 2 changed outcome between the repeats.
    assert group["unstable_questions"] == [2]
    assert group["relaxed_by_difficulty"]["hard"]["mean"] == pytest.approx(0.5)
    assert group["mismatched_fields"] == []


def test_languages_and_setups_are_separate_groups():
    runs = [
        fake_run("olist", "hu", {1: True}),
        fake_run("olist", "en", {1: True}),
        fake_run("olist", "hu", {1: True}, correction=2),
    ]

    assert len(summarize(runs)) == 3


def test_different_prompts_in_one_group_are_flagged():
    runs = [
        fake_run("f1", "hu", {1: True}, prompt="old"),
        fake_run("f1", "hu", {1: True}, prompt="new"),
    ]

    [group] = summarize(runs)

    assert group["mismatched_fields"] == ["prompt_sha256"]
