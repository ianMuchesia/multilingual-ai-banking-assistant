"""SetFit-style contrastive fine-tuning of EmbeddingGemma on the intent labels.

    1. Split train.json: a stratified calibration share (by intent AND language, fixed
       seed) is held out and saved; the encoder never sees it. scripts.evaluate uses it
       to choose threshold/margin for gemma-ft, because held-out scores on sentences
       the encoder was trained on would be optimistic.
    2. Build pairs from the rest: same intent = positive (target cosine 1.0), different
       intent = negative (target 0.0). Each round gives every sentence one of each.
    3. Train with CosineSimilarityLoss (as SetFit does), AdamW, the task prefix applied
       to every input exactly as at inference. LoRA by default; full fine-tuning optional.
    4. Save the adapter (or the full model), calibration.json and metadata.json.

Never reads test.json or test_synthetic.json.
"""

import json
import logging
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import peft
import sentence_transformers
import torch
import transformers
from datasets import Dataset
from peft import LoraConfig
from sentence_transformers import SentenceTransformer, SentenceTransformerTrainer, SentenceTransformerTrainingArguments
from sentence_transformers.sentence_transformer.losses import CosineSimilarityLoss
from transformers import TrainerCallback, TrainerControl, TrainerState, TrainingArguments, set_seed

from src.config import EmbeddingConfig, FinetuneConfig, GemmaConfig
from src.data import Example, load_examples
from src.embeddings.gemma import _TORCH_DTYPES, load_sentence_transformer
from src.embeddings.gemma_ft import FinetuneMetadata
from src.index import file_sha256

log = logging.getLogger(__name__)

POSITIVE = 1.0
NEGATIVE = 0.0


@dataclass(frozen=True)
class Split:
    finetune: list[Example]     # the encoder trains on these
    calibration: list[Example]  # held out from fine-tuning; used only to tune the router's dials


# ---- data ----

def split_calibration(examples: list[Example], fraction: float, seed: int) -> Split:
    """Stratified by (intent, language): each group gives round(fraction * size) sentences.

    A group of one stays in the fine-tuning set. Deterministic for a given seed and train.json.
    """
    if not 0.0 < fraction < 1.0:
        raise ValueError(f"calibration fraction must be between 0 and 1, got {fraction}")
    groups: dict[tuple[str, str], list[Example]] = defaultdict(list)
    for example in examples:
        groups[(example.intent, example.lang)].append(example)

    rng = random.Random(seed)
    held_out: set[str] = set()
    for key in sorted(groups):
        group = sorted(groups[key], key=lambda ex: ex.text)  # independent of file order
        rng.shuffle(group)
        take = round(fraction * len(group)) if len(group) > 1 else 0
        held_out.update(ex.text for ex in group[:take])

    return Split(
        finetune=[ex for ex in examples if ex.text not in held_out],
        calibration=[ex for ex in examples if ex.text in held_out],
    )


def examples_to_json(examples: list[Example]) -> dict[str, list[dict[str, str]]]:
    """Same format as train.json, so src.data.load_examples reads it back."""
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for ex in examples:
        grouped[ex.intent].append({"text": ex.text, "lang": ex.lang})
    return dict(grouped)


def make_pairs(examples: list[Example], rounds: int, seed: int) -> Dataset:
    """SetFit pair sampling: per round, every sentence gets one positive and one negative partner."""
    by_intent: dict[str, list[str]] = defaultdict(list)
    for ex in examples:
        by_intent[ex.intent].append(ex.text)
    intents = sorted(by_intent)
    if len(intents) < 2:
        raise ValueError("contrastive fine-tuning needs at least two intents")

    rng = random.Random(seed)
    rows: list[tuple[str, str, float]] = []
    for _ in range(rounds):
        for ex in examples:
            positives = [t for t in by_intent[ex.intent] if t != ex.text]
            if positives:
                rows.append((ex.text, rng.choice(positives), POSITIVE))
            other = rng.choice([i for i in intents if i != ex.intent])
            rows.append((ex.text, rng.choice(by_intent[other]), NEGATIVE))
    rng.shuffle(rows)

    return Dataset.from_dict({
        "sentence1": [a for a, _, _ in rows],
        "sentence2": [b for _, b, _ in rows],
        "label": [label for _, _, label in rows],
    })


# ---- model ----

def build_model(gemma: GemmaConfig, config: FinetuneConfig) -> SentenceTransformer:
    """Base EmbeddingGemma in float32, with a fresh LoRA adapter unless full fine-tuning."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    log.info("loading %s on %s (%s) for %s fine-tuning", gemma.model_id, device, config.dtype, config.mode)
    model = load_sentence_transformer(gemma.model_id, device, _TORCH_DTYPES[config.dtype], gemma.local_only)

    if config.lora:
        model.add_adapter(
            LoraConfig(
                r=config.lora_r,
                lora_alpha=config.lora_alpha,
                lora_dropout=config.lora_dropout,
                target_modules=list(config.lora_target_modules),
                bias="none",
            )
        )
        # Only the adapter trains; the base weights, pooling and projections stay frozen.
        for name, param in model.named_parameters():
            param.requires_grad = "lora_" in name

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    if trainable == 0:
        raise RuntimeError("no trainable parameters: check lora_target_modules against the model's layer names")
    log.info("trainable parameters: %d of %d (%.2f%%)", trainable, total, 100 * trainable / total)
    return model


class LogProgress(TrainerCallback):
    """Send the Trainer's loss / learning-rate reports to our logger."""

    def on_log(
        self,
        args: TrainingArguments,
        state: TrainerState,
        control: TrainerControl,
        logs: dict[str, float] | None = None,
        **kwargs: object,
    ) -> None:
        if logs:
            values = ", ".join(f"{k} {v:.4g}" if isinstance(v, float) else f"{k} {v}" for k, v in logs.items())
            log.info("step %d/%d: %s", state.global_step, state.max_steps, values)


def train(model: SentenceTransformer, pairs: Dataset, config: FinetuneConfig, prefix: str) -> None:
    args = SentenceTransformerTrainingArguments(
        output_dir=str(config.checkpoint_dir),
        num_train_epochs=config.epochs,
        per_device_train_batch_size=config.batch_size,
        learning_rate=config.learning_rate,
        weight_decay=config.weight_decay,
        warmup_steps=config.warmup_ratio,  # a float below 1 is a ratio of total steps
        optim="adamw_torch",
        seed=config.seed,
        data_seed=config.seed,
        logging_steps=config.logging_steps,
        save_strategy="no",
        report_to="none",
        # The same task prefix the router uses at inference, prepended to every sentence.
        prompts=prefix,
    )
    trainer = SentenceTransformerTrainer(
        model=model,
        args=args,
        train_dataset=pairs,
        loss=CosineSimilarityLoss(model),
        callbacks=[LogProgress()],
    )
    trainer.train()


def save_model(model: SentenceTransformer, config: FinetuneConfig) -> None:
    if config.lora:
        # Adapter weights + adapter_config.json only; the base model stays in the Hugging Face cache.
        model.transformers_model.save_pretrained(str(config.adapter_dir))
        log.info("saved LoRA adapter to %s", config.adapter_dir)
    else:
        model.save_pretrained(str(config.full_model_dir))
        log.info("saved full model to %s", config.full_model_dir)


def hyperparameters(config: FinetuneConfig) -> dict[str, object]:
    params: dict[str, object] = {
        "mode": config.mode,
        "loss": "CosineSimilarityLoss (positive 1.0, negative 0.0)",
        "optimizer": "adamw_torch",
        "epochs": config.epochs,
        "batch_size": config.batch_size,
        "learning_rate": config.learning_rate,
        "weight_decay": config.weight_decay,
        "warmup_ratio": config.warmup_ratio,
        "pair_rounds": config.pair_rounds,
        "calibration_fraction": config.calibration_fraction,
        "seed": config.seed,
        "dtype": config.dtype,
    }
    if config.lora:
        params.update({
            "lora_r": config.lora_r,
            "lora_alpha": config.lora_alpha,
            "lora_dropout": config.lora_dropout,
            "lora_target_modules": list(config.lora_target_modules),
        })
    return params


# ---- the whole run ----

def run_finetune(
    train_path: Path, gemma: GemmaConfig, embedding: EmbeddingConfig, config: FinetuneConfig
) -> FinetuneMetadata:
    """Split, train, save. Returns the metadata written to models/gemma-ft/metadata.json."""
    set_seed(config.seed)
    train_sha256 = file_sha256(train_path)
    examples = load_examples(train_path)
    split = split_calibration(examples, config.calibration_fraction, config.seed)
    log.info(
        "%d train sentences: %d for fine-tuning, %d held out for calibration",
        len(examples), len(split.finetune), len(split.calibration),
    )

    pairs = make_pairs(split.finetune, config.pair_rounds, config.seed)
    positives = sum(label == POSITIVE for label in pairs["label"])
    log.info("%d pairs (%d positive, %d negative)", len(pairs), positives, len(pairs) - positives)

    model = build_model(gemma, config)
    started = datetime.now()
    train(model, pairs, config, embedding.prefix)
    log.info("training took %.1f min", (datetime.now() - started).total_seconds() / 60)

    config.output_dir.mkdir(parents=True, exist_ok=True)
    save_model(model, config)
    config.calibration_file.write_text(
        json.dumps(examples_to_json(split.calibration), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info("saved %d calibration sentences to %s", len(split.calibration), config.calibration_file)

    metadata = FinetuneMetadata(
        base_model=gemma.model_id,
        mode=config.mode,
        created=datetime.now().isoformat(timespec="seconds"),
        train_sha256=train_sha256,
        prefix=embedding.prefix,
        calibration_size=len(split.calibration),
        finetune_size=len(split.finetune),
        pairs=len(pairs),
        hyperparameters=hyperparameters(config),
        versions={
            "sentence_transformers": sentence_transformers.__version__,
            "transformers": transformers.__version__,
            "torch": torch.__version__,
            "peft": peft.__version__,
        },
    )
    metadata.save(config.metadata_file)
    log.info("saved %s (model id %s)", config.metadata_file, metadata.model_id)
    log.info("existing gemma-ft indexes are now stale: rebuild them with build_index --backend gemma-ft --force")
    return metadata
