from retrieval import (
    BM25Retriever,
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
