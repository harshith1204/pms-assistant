import os
from typing import List, Optional, Tuple

# Optional heavy deps guarded behind try/except
try:
    from llmlingua import PromptCompressor  # type: ignore
    _HAS_LLMLINGUA = True
except Exception:
    _HAS_LLMLINGUA = False

try:
    from langchain.retrievers.document_compressors import LLMChainExtractor  # type: ignore
    from langchain_core.documents import Document  # type: ignore
    _HAS_LC_COMPRESS = True
except Exception:
    _HAS_LC_COMPRESS = False

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    import numpy as np  # type: ignore
    _HAS_ST = True
except Exception:
    _HAS_ST = False


def _approx_tokens(text: str) -> int:
    if not text:
        return 0
    # ≈4 chars/token heuristic
    return max(1, (len(text) + 3) // 4)


def _split_sentences(text: str) -> List[str]:
    # Lightweight splitter; avoids heavy deps
    import re
    # Split by sentence end markers while keeping reasonable length
    parts = re.split(r"(?<=[\.!?])\s+|\n+", text.strip())
    return [p.strip() for p in parts if p and len(p.strip()) > 2]


_emb_model = None

def _get_embedder() -> Optional[SentenceTransformer]:
    global _emb_model
    if not _HAS_ST:
        return None
    if _emb_model is None:
        model_name = os.getenv("SEM_CACHE_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        try:
            _emb_model = SentenceTransformer(model_name)
        except Exception:
            _emb_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _emb_model


def _cosine(a, b) -> float:
    import numpy as np  # type: ignore
    if a is None or b is None:
        return 0.0
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _compress_with_llmlingua(text: str, query: str, target_tokens: int) -> str:
    if not _HAS_LLMLINGUA:
        return text
    try:
        # LLMLingua accepts a desired compression rate rather than tokens.
        # Estimate rate from current size and target.
        current = max(1, _approx_tokens(text))
        rate = min(0.95, max(0.1, target_tokens / float(current)))
        # Use a general model name; library will pick default if unspecified
        compressor = PromptCompressor(model_name=os.getenv("LLMLINGUA_MODEL", "microsoft/llmlingua-2-mini"), device_map="auto")
        # Some versions expect a dict-style conversation. Provide instruction via query.
        result = compressor.compress_prompt(
            {"role": "user", "content": text},
            instruction=query or "",
            rate=rate,
        )
        compressed = (
            result.get("compressed_prompt")
            or result.get("text")
            or result.get("compressed")
            or text
        )
        return compressed
    except Exception:
        return text


def _compress_with_llm_chain_extractor(text: str, query: str, target_tokens: int, llm=None) -> str:
    if not (_HAS_LC_COMPRESS and llm is not None):
        return text
    try:
        docs = [Document(page_content=text)]
        compressor = LLMChainExtractor.from_llm(llm)
        out_docs = compressor.compress_documents(docs, query)
        combined = "\n".join([d.page_content for d in out_docs]) if out_docs else text
        # Final trim to target tokens by simple truncation if needed
        tokens = _approx_tokens(combined)
        if tokens > target_tokens:
            # Trim by characters with 4 chars/token heuristic
            keep_chars = max(100, target_tokens * 4)
            combined = combined[:keep_chars]
        return combined
    except Exception:
        return text


def _compress_with_embeddings(text: str, query: str, target_tokens: int) -> str:
    # Extract top-N most similar sentences to query
    embedder = _get_embedder()
    if embedder is None:
        return text
    try:
        sentences = _split_sentences(text)
        if not sentences:
            return text
        vecs = embedder.encode(sentences)
        qvec = embedder.encode([query])[0]
        import numpy as np  # type: ignore
        sims = [(_cosine(v, qvec), i) for i, v in enumerate(vecs)]
        sims.sort(reverse=True)
        selected: List[str] = []
        total = 0
        for _, idx in sims:
            s = sentences[idx]
            selected.append(s)
            total += _approx_tokens(s)
            if total >= target_tokens:
                break
        if not selected:
            return text
        return " ".join(selected)
    except Exception:
        return text


def compress_text(text: str, query: str, target_tokens: int, llm=None) -> str:
    if not text:
        return text
    if _approx_tokens(text) <= max(32, target_tokens):
        return text
    # Prefer LLMLingua, then LLMChainExtractor, then embeddings-based sentence selection
    compressed = _compress_with_llmlingua(text, query, target_tokens)
    if _approx_tokens(compressed) > target_tokens and llm is not None:
        compressed2 = _compress_with_llm_chain_extractor(compressed, query, target_tokens, llm)
        compressed = compressed2
    if _approx_tokens(compressed) > target_tokens:
        compressed = _compress_with_embeddings(compressed, query, target_tokens)
    return compressed


def compress_texts(texts: List[str], query: str, target_total_tokens: int, llm=None) -> List[str]:
    if not texts:
        return []
    # Allocate budget roughly evenly but ensure a floor
    n = len(texts)
    per = max(48, target_total_tokens // max(1, n))
    results: List[str] = []
    for t in texts:
        results.append(compress_text(t, query, per, llm=llm))
    return results
