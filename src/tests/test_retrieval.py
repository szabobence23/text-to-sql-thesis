import os

from retrieval import (
    BM25Retriever,
    EmbeddingRetriever,
    HybridRetriever,
    TableDoc,
    char_ngrams,
    expand_with_bridges,
    repair_mojibake,
    select_tables,
    words,
)


def test_words_split_identifiers():
    assert words("order_items") == ["order", "items"]
    assert words("raceId positionOrder") == ["race", "id", "position", "order"]
    # One-word identifiers stay whole; accented letters are kept.
    assert words("salesorderheader") == ["salesorderheader"]
    assert words("Hány törölt rendelés?") == ["hány", "törölt", "rendelés"]


def test_char_ngrams():
    assert char_ngrams("order", 3) == ["ord", "rde", "der"]
    assert char_ngrams("id", 3) == ["id"]
    assert char_ngrams("order", 0) == ["order"]


def test_table_text_with_and_without_descriptions():
    doc = TableDoc(("sales", "customer"), ("customerid", "storeid"), "Current customer information.")

    assert doc.name == "sales.customer"
    assert doc.text(False) == "sales.customer customerid storeid"
    assert "Current customer information." in doc.text(True)


def test_repair_mojibake():
    assert repair_mojibake("RÃ©sumÃ©s submitted") == "Résumés submitted"
    assert repair_mojibake("Work shift lookup table.") == "Work shift lookup table."


DOCS = [
    TableDoc(("public", "customers"), ("customer_id", "customer_state")),
    TableDoc(("public", "orders"), ("order_id", "customer_id", "order_status")),
    TableDoc(("sales", "salesorderheader"), ("salesorderid", "orderdate", "totaldue")),
]


def test_bm25_ranks_matching_table_first():
    ranking = BM25Retriever(DOCS, ngram=3).rank("How many orders have status canceled?")

    assert ranking[0][0] == ("public", "orders")


def test_ngrams_find_one_word_identifiers():
    # "order header" matches salesorderheader only through its n-grams
    # (the schema name "sales" is left out of the question on purpose).
    question = "order header"
    with_ngrams = BM25Retriever(DOCS, ngram=3).rank(question)
    whole_words = BM25Retriever(DOCS, ngram=0).rank(question)

    assert with_ngrams[0][0] == ("sales", "salesorderheader")
    assert dict(whole_words)[("sales", "salesorderheader")] == 0.0


def test_ranking_is_deterministic_on_ties():
    ranking = BM25Retriever(DOCS, ngram=3).rank("zzzz")

    assert [key for key, _ in ranking] == [
        ("public", "customers"), ("public", "orders"), ("sales", "salesorderheader"),
    ]


GRAPH = {
    "product": {"subcategory"},
    "subcategory": {"product", "category"},
    "category": {"subcategory", "far"},
    "far": {"category"},
}


def test_bridge_table_is_added():
    assert expand_with_bridges(["product", "category"], GRAPH) == [
        "product", "category", "subcategory",
    ]


def test_connected_tables_are_left_alone():
    assert expand_with_bridges(["product", "subcategory"], GRAPH) == ["product", "subcategory"]


def test_paths_longer_than_max_hops_are_not_bridged():
    assert expand_with_bridges(["product", "far"], GRAPH, max_hops=2) == ["product", "far"]
    assert expand_with_bridges(["product", "far"], GRAPH, max_hops=3) == [
        "product", "far", "subcategory", "category",
    ]


def test_select_tables():
    ranking = [("a", 3.0), ("b", 2.0), ("c", 1.0)]

    assert select_tables(ranking, 2) == ["a", "b"]
    assert select_tables(ranking, 2, {"a": {"x"}, "x": {"a", "b"}, "b": {"x"}}, fk_expansion=True) == [
        "a", "b", "x",
    ]


def test_prose_reads_as_sentences():
    doc = TableDoc(("sales", "customer"), ("customerid", "storeid"), "Current customer information.")

    assert doc.prose(False) == "Table sales.customer. Columns: customerid, storeid."
    assert doc.prose(True).startswith("Table sales.customer. Current customer information.")


class FakeEmbedder:
    """Embeds a text as counts of a few keywords; records every call."""

    KEYWORDS = ["customer", "order", "vendor"]

    def __init__(self):
        self.calls = []

    def __call__(self, model, texts):
        self.calls.append(list(texts))
        return [[t.lower().count(k) + 0.01 for k in self.KEYWORDS] for t in texts]


def test_embedding_ranks_by_cosine_similarity():
    retriever = EmbeddingRetriever(DOCS, embed=FakeEmbedder())

    assert retriever.rank("which vendor has the most order lines")[0][0] in {
        ("public", "orders"), ("sales", "salesorderheader"),
    }
    assert retriever.rank("customer list")[0][0] == ("public", "customers")


def test_table_embeddings_are_cached(tmp_path):
    first = FakeEmbedder()
    EmbeddingRetriever(DOCS, embed=first, cache_dir=str(tmp_path), digest="d1")
    second = FakeEmbedder()
    EmbeddingRetriever(DOCS, embed=second, cache_dir=str(tmp_path), digest="d1")

    assert len(first.calls) == 1
    assert second.calls == []  # loaded from the cache

    # A different model digest must not reuse the cached vectors.
    third = FakeEmbedder()
    EmbeddingRetriever(DOCS, embed=third, cache_dir=str(tmp_path), digest="d2")
    assert len(third.calls) == 1
    assert len(os.listdir(tmp_path)) == 2


class FixedRetriever:
    def __init__(self, order):
        self.order = order

    def rank_many(self, questions):
        return [[(key, 0.0) for key in self.order] for _ in questions]


def test_hybrid_uses_reciprocal_rank_fusion():
    # a: ranks 1 and 3; b: ranks 2 and 1; c: ranks 3 and 2.
    hybrid = HybridRetriever([FixedRetriever(["a", "b", "c"]), FixedRetriever(["b", "c", "a"])], c=60)

    [ranking] = hybrid.rank_many(["q"])

    assert [key for key, _ in ranking] == ["b", "a", "c"]
    assert ranking[0][1] == 1 / 62 + 1 / 61
