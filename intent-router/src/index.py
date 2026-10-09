"""The embedding index: example vectors plus their labels, saved to and loaded from cache/."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class EmbeddingIndex:
    vectors: np.ndarray  # (n, dim) float32, unit-length rows
    texts: np.ndarray    # (n,) str
    intents: np.ndarray  # (n,) str, label for each row
    langs: np.ndarray    # (n,) str
    model_id: str
    dim: int
    prefix: str
    source_sha256: str   # hash of the train.json the vectors were built from

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            path,
            vectors=self.vectors,
            texts=self.texts,
            intents=self.intents,
            langs=self.langs,
            model_id=self.model_id,
            dim=self.dim,
            prefix=self.prefix,
            source_sha256=self.source_sha256,
        )

    @classmethod
    def load(cls, path: Path) -> "EmbeddingIndex":
        with np.load(path) as f:
            return cls(
                vectors=f["vectors"],
                texts=f["texts"],
                intents=f["intents"],
                langs=f["langs"],
                model_id=str(f["model_id"]),
                dim=int(f["dim"]),
                prefix=str(f["prefix"]),
                source_sha256=str(f["source_sha256"]),
            )

    @staticmethod
    def is_current(path: Path, source_sha256: str) -> bool:
        """True if an index exists at `path` and was built from a source with this hash."""
        if not path.exists():
            return False
        with np.load(path) as f:
            return str(f["source_sha256"]) == source_sha256
