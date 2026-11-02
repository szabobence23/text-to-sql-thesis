"""
Solved example questions of a dataset (datasets/<name>/examples.json).

Each example is a question (in several languages) with a correct SQL
query; the tables it needs come from the SQL, the same way the oracle
schema reads them from a ground truth. For a new question the most
similar examples are found by embedding similarity and shown to the
model (pipeline: selection_examples).

Kept apart from the test cases on purpose: examples are what the system
may show the model, test cases never are, so an example must not be a
rewording of a test question.
"""

import json
import os
from dataclasses import dataclass

from retrieval import EMBEDDING_CACHE_DIR, _normalize, cached_embeddings, ollama_embed
from sql_tables import tables_in_sql


@dataclass(frozen=True)
class Example:
    id: int
    questions: tuple  # (language, question) pairs
    sql: str
    tables: tuple  # (schema, table) pairs the SQL reads, sorted


def load_examples(path) -> list[Example]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as file:
        items = json.load(file)
    return [
        Example(
            id=item["id"],
            questions=tuple(sorted(item["question"].items())),
            sql=item["sql"],
            tables=tuple(sorted(tables_in_sql(item["sql"]))),
        )
        for item in items
    ]


@dataclass(frozen=True)
class Match:
    example: Example
    question: str  # the example's wording closest to the new question
    score: float


def format_sql_examples(matches):
    """The examples for the SQL prompt: question and SQL, one block each."""
    return "\n\n".join(f"Question: {m.question}\nSQL: {m.example.sql}" for m in matches)


class ExampleRetriever:
    """
    Cosine similarity between the new question and every wording of every
    example; an example scores with its closest wording, so a Hungarian
    question meets the Hungarian wording rather than a translation.
    """

    def __init__(self, examples, model="bge-m3", digest=None,
                 cache_dir=EMBEDDING_CACHE_DIR, embed=ollama_embed):
        if not examples:
            raise ValueError("No examples to search")
        self.examples = examples
        self.model = model
        self.embed = embed
        self.wordings = [(i, q) for i, e in enumerate(examples) for _, q in e.questions]
        texts = [q for _, q in self.wordings]
        self.vectors = [_normalize(v) for v in cached_embeddings(embed, model, texts, cache_dir, digest)]

    def similar(self, question, n) -> list[Match]:
        """The n most similar examples, best first (ties by id)."""
        q = _normalize(self.embed(self.model, [question])[0])
        best = {}
        for (index, wording), vector in zip(self.wordings, self.vectors):
            score = sum(a * b for a, b in zip(q, vector))
            if index not in best or score > best[index][1]:
                best[index] = (wording, score)
        ranked = sorted(best.items(), key=lambda item: (-item[1][1], self.examples[item[0]].id))
        return [Match(self.examples[i], wording, score) for i, (wording, score) in ranked[:n]]
