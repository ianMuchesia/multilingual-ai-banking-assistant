"""Merge the LoRA adapter into the base model, and prove the vectors didn't change.

    HF_HUB_OFFLINE=1 python -m scripts.merge_adapter
"""


import sys


import numpy as np
import torch
from peft import PeftModel
from sentence_transformers import SentenceTransformer


from src.config import ROOT, load_settings, with_overrides
from src.data import load_examples
from src.embeddings import make_embedder
from src.embeddings.gemma import load_sentence_transformer



MERGED_DIR = ROOT / "models" / "gemma-ft-merged"
CHECK_SENTENCES = 50
MIN_COSINE = 0.9999


settings = with_overrides(load_settings(),gemma_local_only=True)
texts = [ex.text for ex in load_examples(settings.paths.train)][:CHECK_SENTENCES]

# 1. Vectors from the book + sticky notes
adapter_embedder = make_embedder("gemma-ft", settings)
vectors_before = adapter_embedder.embed(texts)
prompt_name = adapter_embedder._prompt_name


# 2. Load a clean book, then write the notes into it
model = load_sentence_transformer(settings.gemma.model_id, "cpu", torch.float32, True)
peft_model = PeftModel.from_pretrained(model.transformers_model, str(settings.finetune.adapter_dir))
peft_model.merge_and_unload()





leftover = sum("lora_" in name for name, _ in model.named_parameters())
print("LoRA parts left:", leftover)

model.save_pretrained(str(MERGED_DIR))



# 3. Load the saved model back, and compare
merged = SentenceTransformer(str(MERGED_DIR), device="cpu", local_files_only=True)
vectors_after = merged.encode(
    texts,
    prompt_name=prompt_name,
    normalize_embeddings=True,
    truncate_dim=settings.embedding.dim,
    convert_to_numpy=True,
)

cosines = (vectors_before * vectors_after).sum(axis=1)
print(f"cosine mean {cosines.mean():.6f}   min {cosines.min():.6f}")

if leftover or cosines.min() < MIN_COSINE:
    sys.exit("merge FAILED: do not export this model")
print("merge OK:", MERGED_DIR)
