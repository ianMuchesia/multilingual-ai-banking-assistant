"""Shared contract for all embedding backends."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

import numpy as np

from src.config import EmbeddingConfig


class EmbeddingError(RuntimeError):
    """A backend returned vectors that break the contract (wrong count, NaN, zero vector)."""


class QuotaExceededError(RuntimeError):
    """The API refused the request with 429. Callers should stop, not retry."""


class Embedder(ABC):
    """Turns texts into L2-normalised float32 vectors of size `dim`.

    Subclasses implement `_encode` only. `embed` owns the guarantees every
    backend must meet: one row per text, finite values, unit length.
    """

    def __init__(self, model_id: str, embedding: EmbeddingConfig) -> None:
        self.model_id = model_id
        self.dim = embedding.dim
        self.prefix = embedding.active_prefix  # "" when the prefix is switched off

    @abstractmethod
    def _encode(self, texts: list[str]) -> np.ndarray:
        """Embed raw texts with `self.prefix` applied. Returns shape (len(texts), dim)."""

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        texts = list(texts)
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)

        vectors = np.asarray(self._encode(texts), dtype=np.float32)
        self._validate(vectors, expected_rows=len(texts))
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

    def _validate(self, vectors: np.ndarray, expected_rows: int) -> None:
        if vectors.ndim != 2 or vectors.shape[0] != expected_rows:
            raise EmbeddingError(
                f"{self.model_id}: sent {expected_rows} texts but got back shape {vectors.shape}. "
                "One vector per text is required."
            )
        if vectors.shape[1] != self.dim:
            raise EmbeddingError(f"{self.model_id}: expected vectors of size {self.dim}, got {vectors.shape[1]}")
        if not np.all(np.isfinite(vectors)):
            bad = int(np.sum(~np.all(np.isfinite(vectors), axis=1)))
            raise EmbeddingError(f"{self.model_id}: {bad} of {expected_rows} vectors contain NaN or inf")
        if np.any(np.linalg.norm(vectors, axis=1) == 0):
            raise EmbeddingError(f"{self.model_id}: got an all-zero vector")
