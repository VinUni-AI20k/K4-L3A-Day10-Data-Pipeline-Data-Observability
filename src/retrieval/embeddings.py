from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_core.embeddings import Embeddings
import torch
import torch.nn.functional as functional
from transformers import AutoModel, AutoTokenizer


@lru_cache(maxsize=4)
def _load_model(model_name: str) -> tuple[Any, Any]:
    """Load MiniLM without importing SentenceTransformers' training stack.

    SentenceTransformers 6 imports Hugging Face Datasets/PyArrow even for
    inference.  Loading the same model through Transformers keeps this path
    inference-only and works on managed lab machines that block PyArrow DLLs.
    """
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    model.eval()
    return tokenizer, model


class MiniLMEmbeddings(Embeddings):
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.tokenizer, self.model = _load_model(model_name)

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        encoded = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=256,
            return_tensors="pt",
        )
        with torch.inference_mode():
            token_embeddings = self.model(**encoded).last_hidden_state
            attention_mask = encoded["attention_mask"].unsqueeze(-1).expand(token_embeddings.size()).float()
            summed = torch.sum(token_embeddings * attention_mask, dim=1)
            counts = torch.clamp(attention_mask.sum(dim=1), min=1e-9)
            embeddings = functional.normalize(summed / counts, p=2, dim=1)
        return embeddings.cpu().tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text])[0]
