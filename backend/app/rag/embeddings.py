import hashlib
import math
import re
from typing import List


class LocalHashEmbedder:
    """
    Lightweight local embedding model using hashed token frequencies.
    Avoids external embedding API dependencies.
    """

    def __init__(self, dimension: int = 256):
        self.dimension = dimension
        self._token_pattern = re.compile(r"[a-zA-Z0-9_]+")

    def _tokenize(self, text: str) -> List[str]:
        return self._token_pattern.findall((text or "").lower())

    def embed(self, text: str) -> List[float]:
        vector = [0.0] * self.dimension
        tokens = self._tokenize(text)

        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimension
            vector[bucket] += 1.0

        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0.0:
            return vector

        return [v / norm for v in vector]


embedder = LocalHashEmbedder()
