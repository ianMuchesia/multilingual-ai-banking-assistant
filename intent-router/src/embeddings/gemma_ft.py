"""EmbeddingGemma after contrastive fine-tuning on train.json (scripts.finetune), run locally.

Same model, prompt and output as the "gemma" backend; only the weights differ.
LoRA mode loads the base model from the Hugging Face cache and applies the saved
adapter; full mode loads the complete saved model.

model_id records which fine-tuning run produced the vectors, so the router refuses
an index built with an older fine-tuned model.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import torch
from sentence_transformers import SentenceTransformer

from src.config import EmbeddingConfig, FinetuneConfig, GemmaConfig
from src.embeddings.gemma import GemmaEmbedder, load_sentence_transformer

log = logging.getLogger(__name__)

FINETUNE_MODES = ("lora", "full")


@dataclass(frozen=True)
class FinetuneMetadata:
    """models/gemma-ft/metadata.json: what was trained, from what, and how."""

    base_model: str
    mode: str                      # "lora" or "full"
    created: str                   # ISO timestamp; identifies the run
    train_sha256: str              # train.json the model (and the calibration split) came from
    prefix: str
    calibration_size: int
    finetune_size: int             # train sentences the encoder saw
    pairs: int
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    versions: dict[str, str] = field(default_factory=dict)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "FinetuneMetadata":
        if not path.exists():
            raise FileNotFoundError(f"no fine-tuned model at {path.parent}. Run: python -m scripts.finetune")
        with open(path, encoding="utf-8") as f:
            metadata = cls(**json.load(f))
        if metadata.mode not in FINETUNE_MODES:
            raise ValueError(f"{path.name}: mode must be one of {FINETUNE_MODES}, got {metadata.mode!r}")
        return metadata

    @property
    def model_id(self) -> str:
        """e.g. google/embeddinggemma-2+ft-lora@2026-10-09T14:03:11"""
        return f"{self.base_model}+ft-{self.mode}@{self.created}"


class GemmaFtEmbedder(GemmaEmbedder):
    def __init__(self, config: GemmaConfig, embedding: EmbeddingConfig, finetune: FinetuneConfig) -> None:
        # Read before the base class loads the model: _load() needs them.
        self._finetune = finetune
        self._metadata = FinetuneMetadata.load(finetune.metadata_file)
        if self._metadata.base_model != config.model_id:
            raise ValueError(
                f"{finetune.output_dir.name} was fine-tuned from {self._metadata.base_model}, "
                f"but the configured base model is {config.model_id}. Fine-tune again."
            )
        if self._metadata.prefix != embedding.prefix:
            raise ValueError(
                f"{finetune.output_dir.name} was trained with prefix {self._metadata.prefix!r}, "
                f"config has {embedding.prefix!r}. Fine-tune again."
            )
        super().__init__(config, embedding)
        self.model_id = self._metadata.model_id
        if not self.prefix:
            log.warning("gemma-ft was trained WITH the task prefix; vectors without it are off-distribution")

    def _load(self, config: GemmaConfig, device: str, dtype: torch.dtype) -> SentenceTransformer:
        if self._metadata.mode == "full":
            log.info("loading fine-tuned model from %s", self._finetune.full_model_dir)
            return load_sentence_transformer(str(self._finetune.full_model_dir), device, dtype, local_only=True)

        model = load_sentence_transformer(config.model_id, device, dtype, config.local_only)
        log.info("applying LoRA adapter from %s", self._finetune.adapter_dir)
        model.load_adapter(str(self._finetune.adapter_dir))
        return model
