"""Export the merged model to ONNX, shrink it to INT8, and check the vectors.

    HF_HUB_OFFLINE=1 python -m scripts.export_onnx
"""

import sys

import numpy as np
import onnxruntime as ort
import torch
import torch.nn as nn
import torch.nn.functional as F
from onnxruntime.quantization import quantize_dynamic, QuantType
from sentence_transformers import SentenceTransformer



from src.config import ROOT, load_settings
from src.data import load_examples

MERGED_DIR = ROOT / "models" / "gemma-ft-merged"
ONNX_DIR = ROOT / "models" / "gemma-ft-onnx"
PROMPT_NAME = "Classification"
CHECK_SENTENCES = 100
MIN_COSINE_FP32 = 0.9999


class EmbeddingModel(nn.Module):
    """Text ids in, one sentence vector out. The same steps as Sentence Transformers."""

    def __init__(self, transformer):
        super().__init__()
        self.transformer = transformer

    def forward(self, input_ids, attention_mask):
        tokens = self.transformer(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        weights = attention_mask.unsqueeze(-1).to(tokens.dtype)
        pooled = (tokens * weights).sum(dim=1) / weights.sum(dim=1)  # mean of the real tokens
        return F.normalize(pooled, dim=-1)  # length 1
    
    
    
def embed_onnx(session, tokenizer, prompt, texts):
    vectors = []
    
    for text in texts:
        encoded = tokenizer([prompt + text],truncation=True,return_tensors="np")
        
        inputs = {
            "input_ids": encoded["input_ids"].astype(np.int64),
            "attention_mask": encoded["attention_mask"].astype(np.int64),
        }
        
        vectors.append(session.run(None, inputs)[0])
        
    return np.vstack(vectors)



def report(name, path, reference, tokenizer, prompt, texts):
    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    cosines = (embed_onnx(session, tokenizer, prompt, texts) * reference).sum(axis=1)
    
    size_mb = path.stat().st_size / 1e6
    
    print(f"{name}: {size_mb:.0f} MB   cosine mean {cosines.mean():.4f}   min {cosines.min():.4f}")
    return cosines



settings = load_settings()
texts = [ex.text for ex in load_examples(settings.paths.train)][:CHECK_SENTENCES]

model = SentenceTransformer(str(MERGED_DIR), device="cpu", local_files_only=True)
tokenizer = model.tokenizer
prompt = model.prompts[PROMPT_NAME]
reference = model.encode(texts, prompt_name=PROMPT_NAME, normalize_embeddings=True, convert_to_numpy=True)


ONNX_DIR.mkdir(parents=True, exist_ok=True)
fp32_path = ONNX_DIR / "model.onnx"
int8_path = ONNX_DIR / "model_int8.onnx"
sample = tokenizer([prompt + text for text in texts[:2]], padding=True, return_tensors="pt")
torch.onnx.export(
    EmbeddingModel(model.transformers_model).eval(),
    (sample["input_ids"], sample["attention_mask"]),
    str(fp32_path),
    input_names=["input_ids", "attention_mask"],
    output_names=["embedding"],
    dynamic_axes={
        "input_ids": {0: "batch", 1: "tokens"},
        "attention_mask": {0: "batch", 1: "tokens"},
        "embedding": {0: "batch"},
    },
    opset_version=18,
    dynamo=False,
)


quantize_dynamic(
    str(fp32_path),
    str(int8_path),
    weight_type=QuantType.QInt8,
    op_types_to_quantize=["MatMul"],
)

fp32_cosines = report("onnx fp32", fp32_path, reference, tokenizer, prompt, texts)
report("onnx int8", int8_path, reference, tokenizer, prompt, texts)

if fp32_cosines.min() < MIN_COSINE_FP32:
    sys.exit("export FAILED: the ONNX model does not match the merged model")
print("export OK:", ONNX_DIR)



