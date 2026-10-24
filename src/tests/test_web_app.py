import pytest
from fastapi.testclient import TestClient

from chat_store import ChatStore
from web_app import create_app, title_of


@pytest.fixture
def client(tmp_path):
    asked = []

    def fake_answer(dataset, question):
        asked.append((dataset, question))
        return "99 441 rendelés van.", {"sql": "SELECT COUNT(*) FROM orders;", "columns": ["count"], "rows": [[99441]]}

    app = create_app(ChatStore(str(tmp_path / "chats.sqlite3")), answer=fake_answer)
    client = TestClient(app)
    client.asked = asked
    return client


def test_page_and_datasets_are_served(client):
    assert "Text-to-SQL" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200

    datasets = client.get("/api/datasets").json()
    names = [d["name"] for d in datasets["datasets"]]
    assert datasets["default"] in names
    assert "olist" in names
    olist = next(d for d in datasets["datasets"] if d["name"] == "olist")
    assert olist["label"] and olist["summary"]


def test_first_question_starts_a_conversation(client):
    response = client.post("/api/ask", json={"question": "  Hány rendelés van?  ", "dataset": "olist"})

    assert response.status_code == 200
    body = response.json()
    assert body["conversation"]["title"] == "Hány rendelés van?"
    assert body["message"]["content"] == "99 441 rendelés van."
    assert client.asked == [("olist", "Hány rendelés van?")]

    conversation = client.get(f"/api/conversations/{body['conversation']['id']}").json()
    assert [m["role"] for m in conversation["messages"]] == ["user", "assistant"]
    assert conversation["messages"][1]["details"]["rows"] == [[99441]]


def test_conversation_keeps_its_dataset(client):
    first = client.post("/api/ask", json={"question": "Hány rendelés van?", "dataset": "olist"}).json()

    client.post("/api/ask", json={
        "question": "És hány vásárló?",
        "dataset": "f1",
        "conversation_id": first["conversation"]["id"],
    })

    assert client.asked[-1] == ("olist", "És hány vásárló?")


def test_unknown_dataset_and_conversation_are_rejected(client):
    assert client.post("/api/ask", json={"question": "x", "dataset": "nincs_ilyen"}).status_code == 404
    assert client.post("/api/ask", json={"question": "x", "dataset": "olist", "conversation_id": 999}).status_code == 404
    assert client.post("/api/ask", json={"question": "   ", "dataset": "olist"}).status_code == 422
    assert client.asked == []


def test_delete_conversation(client):
    created = client.post("/api/ask", json={"question": "Hány rendelés van?", "dataset": "olist"}).json()
    conversation_id = created["conversation"]["id"]

    client.delete(f"/api/conversations/{conversation_id}")

    assert client.get(f"/api/conversations/{conversation_id}").status_code == 404
    assert client.get("/api/conversations").json() == []


def test_long_questions_get_a_short_title():
    title = title_of("Melyik " * 30)

    assert len(title) == 48
    assert title.endswith("…")
