"""All configuration in one place: paths, model ids, embedding parameters, API limits, router dials.

Code never hardcodes these values; it receives them from `load_settings()` and
`load_router_config()`. Secrets come from the environment (.env). Router thresholds
live in config/router.json because they are tuned per backend (step 6 calibrates them).
The defaults are the safe production values. `with_overrides()` exists so
experiment scripts can change them deliberately.
"""

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

GEMMA_DTYPES = ("auto", "float32", "bfloat16", "float16")
SPLITS = ("train", "test", "test_synthetic")
TEST_SPLITS = ("test", "test_synthetic")  # exams: never used for training or tuning
SCORING_METHODS = ("max", "topk_mean", "centroid", "logreg", "mlp")


@dataclass(frozen=True)
class Paths:
    intents: Path = ROOT / "data" / "intents.json"
    train: Path = ROOT / "data" / "examples" / "train.json"
    test: Path = ROOT / "data" / "examples" / "test.json"
    test_synthetic: Path = ROOT / "data" / "examples" / "test_synthetic.json"  # written by a different model
    cache: Path = ROOT / "cache"
    eval_results: Path = ROOT / "eval" / "results"
    router_config: Path = ROOT / "config" / "router.json"
    bank_config: Path = ROOT / "config" / "bank.json"  # which bank "we" are, for the bank rule

    def examples(self, split: str) -> Path:
        return {"train": self.train, "test": self.test, "test_synthetic": self.test_synthetic}[split]

    def index_file(self, backend: str, dim: int, split: str = "train") -> Path:
        """cache/gemma_768.npz for train, cache/gemma_768_test.npz for test."""
        suffix = "" if split == "train" else f"_{split}"
        return self.cache / f"{backend}_{dim}{suffix}.npz"


@dataclass(frozen=True)
class EmbeddingConfig:
    dim: int = 768
    # Prepended to every text, for training examples and live messages alike.
    prefix: str = "task: classification | query: "
    use_prefix: bool = True  # False only for experiments

    @property
    def active_prefix(self) -> str:
        return self.prefix if self.use_prefix else ""


@dataclass(frozen=True)
class GemmaConfig:
    model_id: str = "google/embeddinggemma-2"
    # Name of the model's built-in prompt that applies EmbeddingConfig.prefix.
    prompt_name: str = "Classification"
    # "auto" = bfloat16 on a GPU that supports it, else float32.
    # "float16" is known to give NaN / degraded vectors; allowed only to demonstrate that.
    dtype: str = "auto"
    # Load only from the local Hugging Face cache, never contact the Hub.
    # Without it, a machine with no internet wastes ~19s retrying before loading.
    local_only: bool = False


@dataclass(frozen=True)
class GeminiConfig:
    api_key: str = ""
    model_id: str = "gemini-embedding-2"
    batch_size: int = 25
    # Free tier counts each text as one request, max 100/minute: 25 texts every ~15s.
    batch_pause_s: float = 16.0
    max_tries: int = 5
    # Send each text as its own Content. False reproduces the bug where a list of
    # strings comes back as ONE aggregated vector; only for experiments.
    wrap_contents: bool = True


@dataclass(frozen=True)
class FinetuneConfig:
    """Contrastive (SetFit-style) fine-tuning of EmbeddingGemma -> the "gemma-ft" backend.

    Pairs come from the intent labels: same intent = positive (target cosine 1),
    different intent = negative (target 0). The task prefix (EmbeddingConfig.prefix)
    is applied during training too, so training and inference see the same input.
    """

    output_dir: Path = ROOT / "models" / "gemma-ft"
    # Share of train.json held out from fine-tuning, stratified by intent and language.
    # Only the evaluation of gemma-ft uses it (to choose threshold/margin honestly).
    calibration_fraction: float = 0.2
    seed: int = 42
    dtype: str = "float32"            # train in float32 on CPU; bfloat16/float16 hurt stability
    lora: bool = True                 # False = full fine-tuning (--full)
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.1
    lora_target_modules: tuple[str, ...] = (
        "q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj",
    )
    epochs: int = 1
    batch_size: int = 16              # pairs per step; two short sentences each, fine on CPU
    lora_learning_rate: float = 1e-4
    full_learning_rate: float = 2e-5
    weight_decay: float = 0.01
    warmup_ratio: float = 0.1
    # SetFit "num_iterations": each round gives every sentence one positive and one negative pair.
    pair_rounds: int = 5
    logging_steps: int = 10

    @property
    def learning_rate(self) -> float:
        return self.lora_learning_rate if self.lora else self.full_learning_rate

    @property
    def mode(self) -> str:
        return "lora" if self.lora else "full"

    @property
    def adapter_dir(self) -> Path:
        """LoRA mode: adapter weights only; the base model comes from the Hugging Face cache."""
        return self.output_dir / "adapter"

    @property
    def full_model_dir(self) -> Path:
        """Full mode: a complete SentenceTransformer model."""
        return self.output_dir / "model"

    @property
    def metadata_file(self) -> Path:
        return self.output_dir / "metadata.json"

    @property
    def calibration_file(self) -> Path:
        return self.output_dir / "calibration.json"

    @property
    def checkpoint_dir(self) -> Path:
        """Trainer scratch directory (no checkpoints are saved, but the Trainer requires one)."""
        return self.output_dir / "trainer"


@dataclass(frozen=True)
class Settings:
    paths: Paths
    embedding: EmbeddingConfig
    gemma: GemmaConfig
    gemini: GeminiConfig
    finetune: FinetuneConfig


@dataclass(frozen=True)
class RouterConfig:
    """Decision dials for one backend. Gemma and Gemini score on different scales."""

    threshold: float     # best intent score must reach this to route without the LLM
    margin: float        # best intent must beat the second-best by at least this much
    scoring: str = "topk_mean"
    k: int = 3           # examples averaged per intent for "topk_mean"
    action_guard: bool = True
    rules: bool = True   # bank rule + statement rule (src/rules.py); off only to measure their effect

    def __post_init__(self) -> None:
        if self.scoring not in SCORING_METHODS:
            raise ValueError(f"scoring must be one of {SCORING_METHODS}, got {self.scoring!r}")
        if self.k < 1:
            raise ValueError(f"k must be at least 1, got {self.k}")


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    return Settings(
        paths=Paths(),
        embedding=EmbeddingConfig(),
        gemma=GemmaConfig(),
        gemini=GeminiConfig(api_key=os.environ.get("GEMINI_API_KEY", "").strip()),
        finetune=FinetuneConfig(),
    )


def load_router_config(path: Path, backend: str, scoring: str | None = None) -> RouterConfig:
    """Read config/router.json.

    Shared keys (scoring, k, action_guard) at the top level; threshold and margin per
    backend AND per scoring method, because cosine scores and classifier probabilities
    live on different scales:  {"gemma": {"topk_mean": {"threshold": .., "margin": ..}, ...}}
    `scoring` overrides the default scoring method from the file.
    """
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    scoring = scoring or raw.get("scoring", "topk_mean")
    dials = raw.get(backend, {}).get(scoring)
    if dials is None:
        raise ValueError(f"{path.name} has no threshold/margin for backend {backend!r}, scoring {scoring!r}")
    return RouterConfig(
        threshold=dials["threshold"],
        margin=dials["margin"],
        scoring=scoring,
        k=raw.get("k", 3),
        action_guard=raw.get("action_guard", True),
        rules=raw.get("rules", True),
    )


def with_overrides(
    settings: Settings,
    *,
    dim: int | None = None,
    use_prefix: bool | None = None,
    gemma_dtype: str | None = None,
    gemma_local_only: bool | None = None,
    gemini_wrap_contents: bool | None = None,
    finetune_full: bool | None = None,
    finetune_epochs: int | None = None,
    finetune_batch_size: int | None = None,
    finetune_pair_rounds: int | None = None,
) -> Settings:
    """Return a copy of `settings` with the given values changed. None means keep the default."""
    embedding = settings.embedding
    if dim is not None:
        embedding = replace(embedding, dim=dim)
    if use_prefix is not None:
        embedding = replace(embedding, use_prefix=use_prefix)

    gemma = settings.gemma
    if gemma_dtype is not None:
        if gemma_dtype not in GEMMA_DTYPES:
            raise ValueError(f"gemma dtype must be one of {GEMMA_DTYPES}, got {gemma_dtype!r}")
        gemma = replace(gemma, dtype=gemma_dtype)
    if gemma_local_only is not None:
        gemma = replace(gemma, local_only=gemma_local_only)

    gemini = settings.gemini
    if gemini_wrap_contents is not None:
        gemini = replace(gemini, wrap_contents=gemini_wrap_contents)

    finetune = settings.finetune
    if finetune_full is not None:
        finetune = replace(finetune, lora=not finetune_full)
    counts = {"epochs": finetune_epochs, "batch_size": finetune_batch_size, "pair_rounds": finetune_pair_rounds}
    for name, value in counts.items():
        if value is not None:
            if value < 1:
                raise ValueError(f"finetune {name} must be at least 1, got {value}")
            finetune = replace(finetune, **{name: value})

    return replace(settings, embedding=embedding, gemma=gemma, gemini=gemini, finetune=finetune)
