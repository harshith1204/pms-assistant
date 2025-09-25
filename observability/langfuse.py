import os
from typing import Any, Dict, Optional, List

try:
    from langfuse import Langfuse
    from langfuse.decorators import observe
    from langfuse.client import StatefulClient
    from langfuse.openai import AsyncOpenAI, OpenAI  # optional import compatibility
except Exception:
    Langfuse = None  # type: ignore
    observe = None  # type: ignore
    StatefulClient = None  # type: ignore
    AsyncOpenAI = None  # type: ignore
    OpenAI = None  # type: ignore


class LangfuseObservability:
    """Small wrapper to lazily init Langfuse and expose helpers.

    Env vars used:
      - LANGFUSE_PUBLIC_KEY
      - LANGFUSE_SECRET_KEY
      - LANGFUSE_HOST (optional)
      - LANGFUSE_ENABLED (optional: "true"/"false")
    """

    def __init__(self) -> None:
        self._client: Optional[StatefulClient] = None
        self._enabled: bool = str(os.getenv("LANGFUSE_ENABLED", "true")).lower() in {"1", "true", "yes"}

    def is_enabled(self) -> bool:
        return self._enabled and Langfuse is not None

    def client(self) -> Optional[StatefulClient]:
        if not self.is_enabled():
            return None
        if self._client is None:
            self._client = Langfuse(
                public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
                secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
                host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
            )
        return self._client

    def langchain_callbacks(self):
        """Return a list with the Langfuse callback handler if available."""
        if not self.is_enabled():
            return []
        try:
            # Lazy import to avoid hard dep if disabled
            from langfuse.callback import CallbackHandler as LangfuseCallbackHandler  # type: ignore

            return [LangfuseCallbackHandler(public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
                                            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
                                            host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"))]
        except Exception:
            return []

    def observe_decorator(self):
        """Return the observe decorator if available, else a no-op decorator."""
        if self.is_enabled() and observe is not None:
            return observe

        # Fallback noop decorator
        def _noop(func):
            async def _aw(*args, **kwargs):
                return await func(*args, **kwargs)

            def _w(*args, **kwargs):
                return func(*args, **kwargs)

            # return same function preserving async
            return func if hasattr(func, "__await__") else func

        return _noop


langfuse_obs = LangfuseObservability()

