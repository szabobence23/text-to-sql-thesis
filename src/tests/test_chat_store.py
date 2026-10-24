from chat_store import ChatStore


def test_messages_are_stored_in_order_with_details(tmp_path):
    store = ChatStore(str(tmp_path / "chats.sqlite3"))
    conversation = store.create_conversation("Hány rendelés van?", "olist")

    store.add_message(conversation, "user", "Hány rendelés van?")
    store.add_message(conversation, "assistant", "99 441 rendelés van.", {"sql": "SELECT COUNT(*) FROM orders;"})

    messages = store.messages(conversation)
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["details"] is None
    assert messages[1]["details"] == {"sql": "SELECT COUNT(*) FROM orders;"}
    assert store.get_conversation(conversation)["dataset"] == "olist"


def test_history_is_most_recently_used_first(tmp_path):
    store = ChatStore(str(tmp_path / "chats.sqlite3"))
    first = store.create_conversation("első", "olist")
    second = store.create_conversation("második", "f1")

    store.add_message(first, "user", "még egy kérdés")

    assert [c["id"] for c in store.list_conversations()][0] == first
    assert {c["id"] for c in store.list_conversations()} == {first, second}


def test_delete_removes_conversation_and_messages(tmp_path):
    store = ChatStore(str(tmp_path / "chats.sqlite3"))
    conversation = store.create_conversation("törlendő", "olist")
    store.add_message(conversation, "user", "kérdés")

    store.delete_conversation(conversation)

    assert store.get_conversation(conversation) is None
    assert store.messages(conversation) == []
