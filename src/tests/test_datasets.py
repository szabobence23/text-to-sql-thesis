import json
import os

import pytest

from dataset_loader import DEFAULT_LANGUAGE, available_datasets, load_dataset
from sql_structural_validator import validate_sql_structure


REQUIRED_CASE_FIELDS = {"id", "question", "category", "difficulty", "ground_truth_sql"}

DATASET_LANGUAGES = [
    (name, language)
    for name in available_datasets()
    for language in load_dataset(name).languages
]


def load_cases(name, language):
    with open(load_dataset(name).test_cases_path(language), encoding="utf-8") as file:
        return json.load(file)


def test_olist_is_available():
    assert "olist" in available_datasets()


def test_unknown_dataset_is_rejected():
    with pytest.raises(ValueError, match="Available"):
        load_dataset("no_such_dataset")


@pytest.mark.parametrize("name", available_datasets())
def test_dataset_is_complete(name):
    dataset = load_dataset(name)

    assert dataset.db_name
    assert os.path.exists(dataset.schema_sql_path)
    assert os.path.exists(dataset.import_sql_path)
    assert DEFAULT_LANGUAGE in dataset.languages


def test_unknown_language_is_rejected():
    with pytest.raises(ValueError, match="Available"):
        load_dataset("olist").test_cases_path("xx")


@pytest.mark.parametrize("name, language", DATASET_LANGUAGES)
def test_test_cases_are_well_formed(name, language):
    cases = load_cases(name, language)

    assert cases

    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids)), "duplicate test case ids"

    for case in cases:
        missing = REQUIRED_CASE_FIELDS - case.keys()
        assert not missing, f"case {case.get('id')}: missing {missing}"

        is_valid, error = validate_sql_structure(case["ground_truth_sql"])
        assert is_valid, f"case {case['id']}: {error}"


@pytest.mark.parametrize("name, language", DATASET_LANGUAGES)
def test_translations_differ_only_in_question(name, language):
    # Otherwise results in different languages are not comparable.
    def without_question(cases):
        return [{k: v for k, v in case.items() if k != "question"} for case in cases]

    assert without_question(load_cases(name, language)) == without_question(
        load_cases(name, DEFAULT_LANGUAGE)
    )
