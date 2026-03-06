from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.db import Base
from app.memory.memory_service import MemoryService
from app.rag.retriever import Retriever
from app.rag.embeddings import embedder


def test_memory_service_isolates_users():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    memory = MemoryService(db)

    memory.save_message("user_a", "user", "alpha private context")
    memory.save_message("user_b", "user", "beta private context")

    user_a_messages = memory.get_recent_messages("user_a", limit=10)
    user_b_messages = memory.get_recent_messages("user_b", limit=10)

    assert len(user_a_messages) == 1
    assert len(user_b_messages) == 1
    assert user_a_messages[0]["content"] == "alpha private context"
    assert user_b_messages[0]["content"] == "beta private context"


def test_retriever_user_filter_prevents_cross_recall(monkeypatch):
    query = "project phoenix update"

    docs = [
        {
            "id": "alice-1",
            "text": "project phoenix update from alice",
            "embedding": embedder.embed("project phoenix update from alice"),
            "metadata": {"user_id": "alice"},
        },
        {
            "id": "legacy-no-user",
            "text": "project phoenix update from legacy record",
            "embedding": embedder.embed("project phoenix update from legacy record"),
            "metadata": {},
        },
        {
            "id": "bob-1",
            "text": "project phoenix update from bob",
            "embedding": embedder.embed("project phoenix update from bob"),
            "metadata": {"user_id": "bob"},
        },
    ]

    class FakeStore:
        @staticmethod
        def all_documents():
            return docs

    import app.rag.retriever as retriever_module

    monkeypatch.setattr(retriever_module, "vector_store", FakeStore())

    retriever = Retriever()
    alice_results = retriever.search(query=query, top_k=5, filters={"user_id": "alice"})
    bob_results = retriever.search(query=query, top_k=5, filters={"user_id": "bob"})

    assert alice_results
    assert bob_results
    assert all(result["metadata"].get("user_id") == "alice" for result in alice_results)
    assert all(result["metadata"].get("user_id") == "bob" for result in bob_results)
