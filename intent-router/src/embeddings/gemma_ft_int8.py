"""The fine-tuned encoder, exported to ONNX with INT8 weights, run with ONNX Runtime."""



import logging

import numpy as np
import onnxruntime as ort
import torch
from transformers import AutoTokenizer

from src.config import ROOT, EmbeddingConfig, FinetuneConfig
from src.embeddings.base import Embedder
from src.embeddings.gemma_ft import FinetuneMetadata

log = logging.getLogger(__name__)


MERGED_DIR = ROOT / "models" / "gemma-ft-merged"  # the tokenizer comes from here
ONNX_FILE = ROOT / "models" / "gemma-ft-onnx" / "model_int8.onnx"


class GemmaFtInt8Embedder(Embedder):
    def __init__(self,embedding: EmbeddingConfig, finetune:FinetuneConfig)->None:
        if not ONNX_FILE.exists():
            raise FileNotFoundError(f"no {ONNX_FILE.name}. Run: python -m scripts.export_onnx")
        
        metadata = FinetuneMetadata.load(finetune.metadata_file)
        super().__init__(f"{metadata.model_id}+onnx-int8", embedding)
        
        self._tokenizer = AutoTokenizer.from_pretrained(str(MERGED_DIR), local_files_only=True)
        options = ort.SessionOptions()
        options.intra_op_num_threads = torch.get_num_threads()  # same thread count as the benchmark
        log.info("loading %s with %d threads", ONNX_FILE.name, options.intra_op_num_threads)
        self._session = ort.InferenceSession(str(ONNX_FILE), options, providers=["CPUExecutionProvider"])
        
        
    def _encode(self, texts: list[str]) -> np.ndarray:
        # One text per call, never a padded batch. INT8 picks its scale from the whole batch,
        # so batching would make a sentence's vector depend on its neighbours.
        vectors = []
        for text in texts:
            encoded = self._tokenizer([self.prefix + text], truncation=True, return_tensors="np")
            inputs = {
                "input_ids": encoded["input_ids"].astype(np.int64),
                "attention_mask": encoded["attention_mask"].astype(np.int64),
            }
            vectors.append(self._session.run(None, inputs)[0])
        return np.vstack(vectors)



