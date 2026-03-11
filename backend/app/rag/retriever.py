import json
import math
from typing import Dict, List, Optional

from app.core.ttl_cache import TTLCache
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

    def _matches_filters(self, metadata: Dict, filters: Optional[Dict]) -> bool:
        if not filters:
            return True

        for key, expected_value in filters.items():
            if metadata.get(key) != expected_value:
                return False

        return True

    def search(self, query: str, top_k: int = 5, filters: Optional[Dict] = None) -> List[Dict]:
        cleaned_query = (query or "").strip()
        # Small TTL cache for repeated queries (e.g., UI retries / follow-ups).
        cache_key = f"{cleaned_query.lower()[:400]}|k={int(top_k)}|f={hash(json.dumps(filters or {}, sort_keys=True, ensure_ascii=False))}"
        cached = _search_cache.get(cache_key)
        if cached is not None:
            return list(cached)

        query_embedding = embedder.embed(cleaned_query)
        docs = vector_store.all_documents()
        filter_user_id = (filters or {}).get("user_id")

        scored = []
        for doc in docs:
            metadata = doc.get("metadata", {})
            if filter_user_id and metadata.get("user_id") != filter_user_id:
                # Hard guard: user-scoped search never returns docs without matching user_id.
                continue
            if not self._matches_filters(metadata, filters):
                continue

            score = _cosine_similarity(query_embedding, doc.get("embedding", []))
            if score > 0:
                scored.append(
                    {
                        "id": doc.get("id"),
                        "text": doc.get("text", ""),
                        "metadata": metadata,
                        "score": score,
                    }
                )

        scored.sort(key=lambda x: x["score"], reverse=True)
        out = scored[: max(1, top_k)]
        try:
            _search_cache.set(cache_key, list(out), ttl_s=25.0)
        except Exception:
            pass
        return out

    def retrieve_relevant_chunks(self, query: str, *, top_k: int = 5, user_id: str | None = None, document_name: str | None = None) -> List[Dict]:
        filters: Dict[str, object] = {"kind": "document_chunk"}
        if user_id:
            filters["user_id"] = user_id
        if document_name:
            filters["document_name"] = document_name
        return self.search(query=query, top_k=top_k, filters=filters)


_search_cache: TTLCache[str, List[Dict]] = TTLCache(ttl_s=25.0, max_items=512)
retriever = Retriever()
