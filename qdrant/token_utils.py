from __future__ import annotations

"""
Token utilities for RAG chunking and budget packing.

This module centralizes token counting and token-based chunking so that both
indexing and retrieval can use consistent logic.

Strategy:
- Prefer Hugging Face tokenizers tied to the embedding model (more faithful to
  the embedder's max sequence length constraints).
- Fall back to tiktoken's cl100k_base for general-purpose token counting when
  an HF tokenizer isn't available or for chat-model-oriented budgeting.
"""

from typing import List, Optional, Protocol
from functools import lru_cache


class TokenCounter(Protocol):
    def count(self, text: str) -> int:  # number of tokens
        ...

    def encode(self, text: str) -> List[int]:  # token ids
        ...

    def decode(self, token_ids: List[int]) -> str:  # text
        ...


class HfTokenCounter:
    def __init__(self, model_name: str) -> None:
        from transformers import AutoTokenizer  # type: ignore

        self.model_name = model_name
        self._tok = AutoTokenizer.from_pretrained(model_name)

    def count(self, text: str) -> int:
        # Avoid special tokens so we measure raw payload cost
        return len(self._tok.encode(text, add_special_tokens=False))

    def encode(self, text: str) -> List[int]:
        return self._tok.encode(text, add_special_tokens=False)

    def decode(self, token_ids: List[int]) -> str:
        return self._tok.decode(token_ids, skip_special_tokens=True, clean_up_tokenization_spaces=True)


class TikTokenCounter:
    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        import tiktoken  # type: ignore

        self._enc = tiktoken.get_encoding(encoding_name)

    def count(self, text: str) -> int:
        return len(self._enc.encode(text))

    def encode(self, text: str) -> List[int]:
        return self._enc.encode(text)

    def decode(self, token_ids: List[int]) -> str:
        return self._enc.decode(token_ids)


@lru_cache(maxsize=8)
def get_hf_counter(model_name: str) -> TokenCounter:
    return HfTokenCounter(model_name)


@lru_cache(maxsize=1)
def get_tiktoken_counter() -> TokenCounter:
    return TikTokenCounter("cl100k_base")


def choose_counter(prefer_hf_model: Optional[str] = None) -> TokenCounter:
    """Choose a token counter.

    - If a huggingface model name is provided and available, use it.
    - Otherwise, fall back to tiktoken's cl100k_base.
    """
    try:
        if prefer_hf_model:
            return get_hf_counter(prefer_hf_model)
    except Exception:
        # Fall back below
        pass
    try:
        return get_tiktoken_counter()
    except Exception:
        # Last-resort ultra-rough estimator
        class RoughCounter:
            def count(self, text: str) -> int:
                # Very rough best-effort: ~1 token per 4 chars
                return max(1, int(len(text) / 4))

            def encode(self, text: str) -> List[int]:
                # Not a real encoding; split by approx token windows
                size = 4
                return list(range(0, max(1, int(len(text) / size))))

            def decode(self, token_ids: List[int]) -> str:
                # Cannot reconstruct faithfully; return empty placeholder
                return ""

        return RoughCounter()  # type: ignore[return-value]


def chunk_by_tokens(
    text: str,
    *,
    counter: TokenCounter,
    chunk_size: int,
    overlap: int = 0,
) -> List[str]:
    """Split text into token-based chunks with token overlap.

    Uses encode/decode for faithful splitting. Overlap is applied in tokens.
    """
    if not text:
        return []
    if chunk_size <= 0:
        return [text]

    ids = counter.encode(text)
    n = len(ids)
    if n <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0
    step = max(1, chunk_size - max(0, overlap))
    while start < n:
        end = min(n, start + chunk_size)
        piece = counter.decode(ids[start:end]).strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = end - max(0, overlap)
    return chunks


def trim_to_token_limit(text: str, *, counter: TokenCounter, max_tokens: int) -> str:
    """Trim text to at most max_tokens using the provided counter."""
    if not text:
        return text
    if max_tokens <= 0:
        return ""
    ids = counter.encode(text)
    if len(ids) <= max_tokens:
        return text
    return counter.decode(ids[:max_tokens]).strip()

