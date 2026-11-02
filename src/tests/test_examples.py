import json

import llm
from examples import ExampleRetriever, format_sql_examples, load_examples


class KeywordEmbedder:
    """Embeds a text as counts of a few keywords; records every call."""

    KEYWORDS = ["vendor", "beszállító", "employee", "dolgozó"]

    def __init__(self):
        self.calls = []

    def __call__(self, model, texts):
        self.calls.append(list(texts))
        return [[t.lower().count(k) + 0.01 for k in self.KEYWORDS] for t in texts]


def write_examples(tmp_path):
    path = tmp_path / "examples.json"
    path.write_text(json.dumps([
        {"id": 1, "question": {"hu": "Melyik beszállító a legjobb?", "en": "Which vendor is best?"},
         "sql": "SELECT name FROM purchasing.vendor;"},
        {"id": 2, "question": {"hu": "Hány dolgozó van?", "en": "How many employees are there?"},
         "sql": "SELECT COUNT(*) FROM humanresources.employee e JOIN person.person p ON p.businessentityid = e.businessentityid;"},
    ]), encoding="utf-8")
    return str(path)


def test_examples_read_their_tables_from_the_sql(tmp_path):
    examples = load_examples(write_examples(tmp_path))

    assert [e.id for e in examples] == [1, 2]
    assert examples[1].tables == (("humanresources", "employee"), ("person", "person"))
    assert dict(examples[0].questions)["hu"] == "Melyik beszállító a legjobb?"


def test_missing_examples_file_means_no_examples(tmp_path):
    assert load_examples(str(tmp_path / "nope.json")) == []


def test_similar_examples_match_the_closest_wording(tmp_path):
    retriever = ExampleRetriever(load_examples(write_examples(tmp_path)), embed=KeywordEmbedder(), cache_dir=None)

    best = retriever.similar("Melyik dolgozó dolgozik a legtöbbet?", 1)[0]

    assert best.example.id == 2
    # The Hungarian question met the Hungarian wording.
    assert best.question == "Hány dolgozó van?"
    assert [m.example.id for m in retriever.similar("vendor list", 2)] == [1, 2]


def test_selection_prompt_gets_examples_only_when_given(monkeypatch):
    prompts = []

    class Response:
        class message:
            content = "orders"
        prompt_eval_count = 1
        eval_count = 1

    monkeypatch.setattr(llm, "_call", lambda messages, settings: prompts.append(messages[0]["content"]) or Response)

    llm.choose_tables("question", "- orders: id", llm.LLMSettings())
    llm.choose_tables("question", "- orders: id", llm.LLMSettings(), examples_text='- "q" -> orders')

    assert prompts[0] == llm.TABLE_SELECTION_TEMPLATE.format(question="question", tables="- orders: id")
    assert 'SIMILAR SOLVED QUESTIONS' in prompts[1]
    assert prompts[1].index('- "q" -> orders') < prompts[1].index("CANDIDATE TABLES:")


def test_sql_examples_are_formatted_as_question_and_sql(tmp_path):
    retriever = ExampleRetriever(load_examples(write_examples(tmp_path)), embed=KeywordEmbedder(), cache_dir=None)

    text = format_sql_examples(retriever.similar("vendor", 1))

    assert text == "Question: Which vendor is best?\nSQL: SELECT name FROM purchasing.vendor;"
