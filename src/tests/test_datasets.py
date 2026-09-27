import json
import os

import pytest

from dataset_loader import available_datasets, load_dataset
from sql_structural_validator import validate_sql_structure


REQUIRED_CASE_FIELDS = {"id", "question", "category", "difficulty", "ground_truth_sql"}


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
    assert os.path.exists(dataset.test_cases_path)


@pytest.mark.parametrize("name", available_datasets())
def test_test_cases_are_well_formed(name):
    with open(load_dataset(name).test_cases_path, encoding="utf-8") as file:
        cases = json.load(file)

    assert cases

    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids)), "duplicate test case ids"

    for case in cases:
        missing = REQUIRED_CASE_FIELDS - case.keys()
        assert not missing, f"case {case.get('id')}: missing {missing}"

        is_valid, error = validate_sql_structure(case["ground_truth_sql"])
        assert is_valid, f"case {case['id']}: {error}"
