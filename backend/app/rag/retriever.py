import math
from typing import Dict, List, Optional

from app.rag.embeddings import embedder
from app.rag.vector_store import vector_store


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if len(a) != len(b):
        return 0.0

    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0

    for i in range(len(a)):
        dot += a[i] * b[i]
        norm_a += a[i] * a[i]
        norm_b += b[i] * b[i]

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


class Retriever:
    """
    RAG retriever that embeds query and ranks stored chunks.
    """

    def add_text(self, text: str, metadata: Optional[Dict] = None) -> str:
        embedding = embedder.embed(text)
        return vector_store.add_document(text=text, embedding=embedding, metadata=metadata)

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        query_embedding = embedder.embed(query)
        docs = vector_store.all_documents()

        scored = []
        for doc in docs:
            score = _cosine_similarity(query_embedding, doc.get("embedding", []))
            if score > 0:
                scored.append(
                    {
                        "id": doc.get("id"),
                        "text": doc.get("text", ""),
                        "metadata": doc.get("metadata", {}),
                        "score": score,
                    }
                )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[: max(1, top_k)]


retriever = Retriever()
