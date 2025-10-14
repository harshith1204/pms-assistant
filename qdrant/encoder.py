from __future__ import annotations

"""
Encoder utilities for Qdrant vector operations.

Provides:
1. SPLADE encoder for sparse vectors
2. SentenceTransformer encoder for dense vectors
"""

from typing import Dict, List, Tuple
import threading
import numpy as np


_encoder_singleton_lock = threading.Lock()
_encoder_singleton: "SpladeEncoder | None" = None
_sentence_encoder_lock = threading.Lock()
_sentence_encoder: "SentenceTransformerEncoder | None" = None


class SpladeEncoder:
    """SPLADE encoder producing sparse (indices, values) vectors."""

    def __init__(self, model_name: str = "naver/splade-cocondenser-ensembledistil") -> None:
        # Lazy imports keep startup fast when SPLADE isn't used
        from transformers import AutoTokenizer, AutoModelForMaskedLM  # type: ignore
        import torch  # type: ignore

        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForMaskedLM.from_pretrained(model_name)
        self.model.eval()
        self.torch = torch

    def encode_text(self, text: str, max_terms: int = 200) -> Dict[str, List[float]]:
        """Encode text to SPLADE sparse representation.

        Returns:
            {"indices": List[int], "values": List[float]}
        """
        if not text or not text.strip():
            return {"indices": [], "values": []}

        torch = self.torch
        # Tokenize and cap to model max length
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )

        with torch.no_grad():
            logits = self.model(**inputs).logits.squeeze(0)  # [seq_len, vocab]
            # SPLADE activation: log(1 + sum(ReLU(logits), dim=seq))
            activated = torch.relu(logits)
            aggregated = torch.log1p(torch.sum(activated, dim=0))  # [vocab]

        # Select top-k terms to keep vector compact
        k = min(max_terms, aggregated.numel())
        values, indices = torch.topk(aggregated, k)

        # Filter out zero or near-zero weights
        mask = values > 0
        values = values[mask]
        indices = indices[mask]

        # Convert to python lists
        indices_list = [int(i) for i in indices.tolist()]
        values_list = [float(v) for v in values.tolist()]

        return {"indices": indices_list, "values": values_list}


def get_splade_encoder() -> SpladeEncoder:
    global _encoder_singleton
    if _encoder_singleton is not None:
        return _encoder_singleton
    with _encoder_singleton_lock:
        if _encoder_singleton is None:
            _encoder_singleton = SpladeEncoder()
        return _encoder_singleton


class SentenceTransformerEncoder:
    """Dense vector encoder using SentenceTransformers."""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        """
        Initialize the sentence transformer encoder.
        
        Args:
            model_name: HuggingFace model name for sentence transformers
        """
        from sentence_transformers import SentenceTransformer
        
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        print(f"✅ Loaded SentenceTransformer model: {model_name}")
    
    def encode(self, text: str | List[str]) -> np.ndarray:
        """
        Encode text to dense vector(s).
        
        Args:
            text: Single text string or list of strings
        
        Returns:
            numpy array of embeddings
        """
        if not text:
            # Return zero vector for empty text
            return np.zeros(768)
        
        return self.model.encode(text, convert_to_numpy=True)
    
    def encode_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Encode multiple texts efficiently in batches.
        
        Args:
            texts: List of text strings
            batch_size: Batch size for encoding
        
        Returns:
            numpy array of embeddings
        """
        return self.model.encode(texts, batch_size=batch_size, convert_to_numpy=True)


def get_sentence_encoder(model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> SentenceTransformerEncoder:
    """Get or create the global sentence encoder instance"""
    global _sentence_encoder
    if _sentence_encoder is not None:
        return _sentence_encoder
    with _sentence_encoder_lock:
        if _sentence_encoder is None:
            _sentence_encoder = SentenceTransformerEncoder(model_name)
        return _sentence_encoder

