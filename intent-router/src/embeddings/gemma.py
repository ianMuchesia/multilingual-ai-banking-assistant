"""EmbeddingGemma, run locally with sentence-transformers."""

import logging

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from src.config import EmbeddingConfig, GemmaConfig
from src.embeddings.base import Embedder

log = logging.getLogger(__name__)

_TORCH_DTYPES = {"float32": torch.float32, "bfloat16": torch.bfloat16, "float16": torch.float16}


def _pick_device(dtype_name: str) -> tuple[str, torch.dtype]:
    """"auto": bfloat16 on a GPU that supports it, else float32 on CPU. Otherwise use what was asked."""
    has_cuda = torch.cuda.is_available()
    if dtype_name == "auto":
        if has_cuda and torch.cuda.is_bf16_supported():
            return "cuda", torch.bfloat16
        return "cpu", torch.float32
    if dtype_name == "float16":
        log.warning("float16 is known to make this model return NaN or degraded vectors")
    return ("cuda" if has_cuda else "cpu"), _TORCH_DTYPES[dtype_name]


def load_sentence_transformer(source: str, device: str, dtype: torch.dtype, local_only: bool) -> SentenceTransformer:
    """Load EmbeddingGemma (a Hub id or a local directory) with text-only weights."""
    return SentenceTransformer(
        source,
        device=device,
        local_files_only=local_only,
        config_kwargs={"vision_config": None, "audio_config": None},  # text-only weights
        model_kwargs={"torch_dtype": dtype},
    )


class GemmaEmbedder(Embedder):
    def __init__(self, config: GemmaConfig, embedding: EmbeddingConfig) -> None:
        super().__init__(config.model_id, embedding)
        # The model applies the prefix through its built-in prompt; no prompt when the prefix is off.
        self._prompt_name = config.prompt_name if self.prefix else None

        device, dtype = _pick_device(config.dtype)
        source = "local cache only" if config.local_only else "hub or local cache"
        log.info("loading %s on %s (%s), %s", self.model_id, device, dtype, source)
        self._model = self._load(config, device, dtype)
        if self._prompt_name:
            self._check_prompt()
        else:
            log.warning("task prefix is OFF")

    def _load(self, config: GemmaConfig, device: str, dtype: torch.dtype) -> SentenceTransformer:
        """The base model. Subclasses (the fine-tuned backend) load something else."""
        return load_sentence_transformer(config.model_id, device, dtype, config.local_only)

    def _check_prompt(self) -> None:
        """The model applies its own prompt; it must be the prefix we use everywhere else."""
        model_prompt = self._model.prompts.get(self._prompt_name)
        if model_prompt != self.prefix:
            raise ValueError(
                f"{self.model_id} prompt {self._prompt_name!r} is {model_prompt!r}, expected {self.prefix!r}"
            )

    def _encode(self, texts: list[str]) -> np.ndarray:
        log.info("embedding %d texts", len(texts))
        return self._model.encode(
            texts,
            prompt_name=self._prompt_name,
            normalize_embeddings=True,
            truncate_dim=self.dim,
            convert_to_numpy=True,
        )
