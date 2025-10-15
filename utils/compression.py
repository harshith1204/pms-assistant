import os
from typing import List

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


def _approx_tokens(text: str) -> int:
    if not text:
        return 0
    # ≈4 chars/token for rough gating only
    return max(1, (len(text) + 3) // 4)


def _compress_with_llmlingua(text: str, query: str, target_tokens: int) -> str:
    """Primary compression using LLMLingua, configured to use Groq when available.

    We attempt to initialize PromptCompressor with Groq's OpenAI-compatible endpoint.
    If unsupported by the installed llmlingua version, we fall back to local model.
    """
    if not _HAS_LLMLINGUA:
        return text
    try:
        current = max(1, _approx_tokens(text))
        rate = min(0.95, max(0.1, target_tokens / float(current)))

        groq_api_key = os.getenv("GROQ_API_KEY")
        groq_api_base = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")
        groq_model = os.getenv("GROQ_LLMINGUA_MODEL", os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"))

        compressor = None
        # First try: pass OpenAI-compatible params
        try:
            compressor = PromptCompressor(
                model_name=groq_model,
                openai_api_key=groq_api_key,
                api_base=groq_api_base,
                provider="openai",
            )
        except TypeError:
            # Fallback to local model if these kwargs aren't supported
            compressor = PromptCompressor(
                model_name=os.getenv("LLMLINGUA_MODEL", "microsoft/llmlingua-2-mini"),
                device_map="auto",
            )

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


def _compress_with_llm_chain_extractor(text: str, query: str, llm=None) -> str:
    if not (_HAS_LC_COMPRESS and llm is not None):
        return text
    try:
        docs = [Document(page_content=text)]
        compressor = LLMChainExtractor.from_llm(llm)
        out_docs = compressor.compress_documents(docs, query)
        combined = "\n".join([d.page_content for d in out_docs]) if out_docs else text
        return combined
    except Exception:
        return text


def compress_text(text: str, query: str, target_tokens: int, llm=None) -> str:
    if not text:
        return text
    # Use LLMLingua first; then LLMChainExtractor as LLM-only fallback
    compressed = _compress_with_llmlingua(text, query, target_tokens)
    if _approx_tokens(compressed) > target_tokens and llm is not None:
        compressed2 = _compress_with_llm_chain_extractor(compressed, query, llm)
        compressed = compressed2 or compressed
    return compressed


def compress_texts(texts: List[str], query: str, target_total_tokens: int, llm=None) -> List[str]:
    if not texts:
        return []
    # Allocate budget evenly
    n = max(1, len(texts))
    per = max(1, target_total_tokens // n)
    return [compress_text(t, query, per, llm=llm) for t in texts]
