"""Embedding backends for the intent router.

    settings = load_settings()
    embedder = make_embedder("gemma", settings)
    vectors = embedder.embed(["what's my balance"])   # (1, 768), unit-length rows
"""

from src.config import Settings
from src.embeddings.base import Embedder, EmbeddingError, QuotaExceededError
from src.embeddings.gemini import GeminiEmbedder
from src.embeddings.gemma import GemmaEmbedder
from src.embeddings.gemma_ft import GemmaFtEmbedder
from src.embeddings.gemma_ft_int8 import GemmaFtInt8Embedder

BACKENDS = ("gemma", "gemma-ft", "gemma-ft-int8","gemini")
# Encoders trained on train.json: evaluation tunes their dials on the held-out calibration split.
FINETUNED_BACKENDS = ("gemma-ft","gemma-ft-int8")


def make_embedder(backend: str, settings: Settings) -> Embedder:
    if backend == "gemma":
        return GemmaEmbedder(settings.gemma, settings.embedding)
    if backend == "gemma-ft":
        return GemmaFtEmbedder(settings.gemma, settings.embedding, settings.finetune)
    if backend == "gemini":
        return GeminiEmbedder(settings.gemini, settings.embedding)
    if backend == "gemma-ft-int8":
        return GemmaFtInt8Embedder(settings.embedding, settings.finetune)

    raise ValueError(f"backend must be one of {BACKENDS}, got {backend!r}")


__all__ = [
    "BACKENDS",
    "FINETUNED_BACKENDS",
    "Embedder",
    "EmbeddingError",
    "GeminiEmbedder",
    "GemmaEmbedder",
    "GemmaFtEmbedder",
    "GemmaFtInt8Embedder",
    "QuotaExceededError",
    "make_embedder",
]
