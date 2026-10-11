"""Offline test features and an explicitly opt-in local semantic backend."""

import hashlib
import re
from typing import Protocol

import numpy as np

SYNONYMS = {
    "summarize": "analyze",
    "summarise": "analyze",
    "explain": "analyze",
    "inspect": "check",
    "examine": "check",
    "review": "check",
    "errors": "error",
    "failures": "error",
    "failure": "error",
    "logs": "log",
    "metrics": "metric",
    "changes": "change",
    "database": "db",
    "postgresql": "postgres",
    "configuration": "config",
    "recent": "recent",
    "healthy": "healthy",
    "normal": "healthy",
    "unhealthy": "unhealthy",
    "abnormal": "unhealthy",
    "unavailable": "unavailable",
    "offline": "unavailable",
    "available": "available",
    "online": "available",
    "timeouts": "timeout",
    "latencies": "latency",
}
FILLER = frozenset(
    {
        "a",
        "an",
        "the",
        "please",
        "is",
        "are",
        "was",
        "were",
        "do",
        "does",
        "can",
        "could",
        "you",
        "of",
        "for",
        "to",
    }
)


def canonical_tokens(text: str) -> tuple[str, ...]:
    words = re.findall(r"[a-z0-9_]+|[<>!=]+", text.lower().replace("n't", " not"))
    return tuple(SYNONYMS.get(word, word) for word in words if word not in FILLER)


def safe_equivalent(left: str, right: str) -> bool:
    """Fail closed when content, polarity, comparison or numeric tokens differ.

    This is a conservative vocabulary guard, not general natural-language entailment.
    It intentionally rejects many legitimate paraphrases rather than bare cosine reuse.
    """
    return canonical_tokens(left) == canonical_tokens(right)


class EmbeddingBackend(Protocol):
    backend_id: str

    def embed(self, text: str) -> np.ndarray: ...


class FakeEmbedder:
    """Deterministic hashed synonym features; testing aid, not learned semantics."""

    backend_id = "fake-synonym-features-v1"

    def embed(self, text: str) -> np.ndarray:
        result = np.zeros(256, dtype=np.float64)
        for token in canonical_tokens(text):
            digest = hashlib.sha256(token.encode()).digest()
            result[int.from_bytes(digest[:4], "big") % len(result)] += 1
        norm = np.linalg.norm(result)
        return result / norm if norm else result


class SentenceTransformerBackend:
    """Lazy backend. Explicit use may acquire weights; basic CI never constructs it."""

    def __init__(
        self, model_name="sentence-transformers/all-MiniLM-L6-v2", *, local_files_only=True
    ):
        self.model_name = model_name
        self.local_files_only = local_files_only
        self.backend_id = "sentence-transformers:" + model_name
        self._model = None

    def embed(self, text: str) -> np.ndarray:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self.model_name, device="cpu", local_files_only=self.local_files_only
            )
        return np.asarray(self._model.encode(text, normalize_embeddings=True), dtype=np.float64)


def cosine(left, right) -> float:
    left, right = np.asarray(left, dtype=np.float64), np.asarray(right, dtype=np.float64)
    if (
        left.shape != right.shape
        or left.ndim != 1
        or not np.all(np.isfinite(left))
        or not np.all(np.isfinite(right))
    ):
        return 0.0
    with np.errstate(over="ignore", invalid="ignore"):
        denominator = np.linalg.norm(left) * np.linalg.norm(right)
        if not denominator or not np.isfinite(denominator):
            return 0.0
        similarity = np.dot(left, right) / denominator
    return float(np.clip(similarity, -1, 1)) if np.isfinite(similarity) else 0.0
