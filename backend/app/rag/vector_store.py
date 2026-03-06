import json
import os
import tempfile
import threading
import uuid
from typing import Dict, List, Optional

from app.config.settings import DATA_DIR


class LocalVectorStore:
    """
    File-backed vector store for local RAG.
    """

    def __init__(self, store_path: Optional[str] = None):
        self.store_path = store_path or os.path.join(DATA_DIR, "rag_store.json")
        self._lock = threading.Lock()
        self._data = {"documents": []}
        self._load()

    def _load(self):
        os.makedirs(os.path.dirname(self.store_path), exist_ok=True)

        if not os.path.exists(self.store_path):
            self._flush()
            return

        with open(self.store_path, "r", encoding="utf-8") as f:
            self._data = json.load(f)

        if "documents" not in self._data:
            self._data = {"documents": []}
            self._flush()

    def _flush(self):
        directory = os.path.dirname(self.store_path)
        os.makedirs(directory, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=directory,
            delete=False
        ) as temp_file:
            json.dump(self._data, temp_file, ensure_ascii=False, indent=2)
            temp_name = temp_file.name

        os.replace(temp_name, self.store_path)

    def add_document(
        self,
        text: str,
        embedding: List[float],
        metadata: Optional[Dict] = None
    ) -> str:
        with self._lock:
            doc_id = str(uuid.uuid4())
            self._data["documents"].append(
                {
                    "id": doc_id,
                    "text": text,
                    "embedding": embedding,
                    "metadata": metadata or {},
                }
            )
            self._flush()
            return doc_id

    def all_documents(self) -> List[Dict]:
        with self._lock:
            return list(self._data.get("documents", []))

    def clear(self):
        with self._lock:
            self._data = {"documents": []}
            self._flush()


vector_store = LocalVectorStore()
