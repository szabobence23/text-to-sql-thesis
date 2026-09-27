"""
Datasets: a database plus everything that belongs to it.

(Not named datasets.py, which would shadow the Hugging Face package.)

Each dataset is a folder under datasets/ (see datasets/README.md):
dataset.json, schema.sql, import.sql, optional hints.txt and
test_cases.json. Switching databases means switching the dataset name.
"""

import json
import os
from dataclasses import dataclass


REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASETS_DIR = os.path.join(REPO_DIR, "datasets")

DEFAULT_DATASET = os.getenv("TEXT2SQL_DATASET", "olist")


@dataclass(frozen=True)
class Dataset:
    name: str
    db_name: str
    description: str
    path: str

    @property
    def hints(self) -> str:
        """Hand-written notes for the prompt; empty if the dataset has none."""
        hints_path = os.path.join(self.path, "hints.txt")

        if not os.path.exists(hints_path):
            return ""

        with open(hints_path, "r", encoding="utf-8") as file:
            # Stripped, so an editor adding a trailing newline does not
            # change the prompt.
            return file.read().strip()

    @property
    def test_cases_path(self) -> str:
        return os.path.join(self.path, "test_cases.json")

    @property
    def schema_sql_path(self) -> str:
        return os.path.join(self.path, "schema.sql")

    @property
    def import_sql_path(self) -> str:
        return os.path.join(self.path, "import.sql")


def available_datasets() -> list[str]:
    return sorted(
        name for name in os.listdir(DATASETS_DIR)
        if os.path.exists(os.path.join(DATASETS_DIR, name, "dataset.json"))
    )


def load_dataset(name: str) -> Dataset:
    path = os.path.join(DATASETS_DIR, name)
    config_path = os.path.join(path, "dataset.json")

    if not os.path.exists(config_path):
        raise ValueError(
            f"Unknown dataset '{name}'. "
            f"Available: {', '.join(available_datasets())}"
        )

    with open(config_path, "r", encoding="utf-8") as file:
        config = json.load(file)

    return Dataset(
        name=name,
        db_name=config["db_name"],
        description=config.get("description", ""),
        path=path,
    )
