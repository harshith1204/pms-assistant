import os
from typing import Dict, List, Optional

try:
    from langchain.memory import ConversationEntityMemory  # type: ignore
    _HAS_LC = True
except Exception:
    _HAS_LC = False

try:
    from langchain_core.messages import SystemMessage  # type: ignore
except Exception:
    class SystemMessage:  # Fallback minimal shim
        def __init__(self, content: str):
            self.content = content


class MemoryManager:
    """Lightweight wrapper that adds entity memory context to each turn.

    Notes:
    - Uses LangChain ConversationEntityMemory when available.
    - State is kept per conversation_id.
    - We purposefully do not duplicate summary memory here because an existing
      rolling summary is already injected upstream.
    """

    def __init__(self) -> None:
        self._entities_by_conv: Dict[str, any] = {}

    def _ensure_entity_memory(self, conversation_id: str, llm) -> Optional[any]:
        if not _HAS_LC or llm is None:
            return None
        mem = self._entities_by_conv.get(conversation_id)
        if mem is None:
            try:
                mem = ConversationEntityMemory(llm=llm)
                self._entities_by_conv[conversation_id] = mem
            except Exception:
                mem = None
        return mem

    def build_context_messages(
        self,
        conversation_id: str,
        user_query: str,
        llm=None,
    ) -> List[SystemMessage]:
        messages: List[SystemMessage] = []
        mem = self._ensure_entity_memory(conversation_id, llm)
        if mem is None:
            return messages
        try:
            # Many LC memories expose load_memory_variables; key often 'entities'
            vars = mem.load_memory_variables({"input": user_query}) or {}
            text = None
            for k in ("entities", "entity_summaries", "history"):
                if isinstance(vars.get(k), str) and vars.get(k).strip():
                    text = vars.get(k)
                    break
            if text:
                messages.append(SystemMessage(content=f"Entity memory (people, projects, etc.):\n{text}"))
        except Exception:
            pass
        return messages

    def save_turn(self, conversation_id: str, user_input: str, assistant_output: str, llm=None) -> None:
        mem = self._ensure_entity_memory(conversation_id, llm)
        if mem is None:
            return
        try:
            mem.save_context({"input": user_input or ""}, {"output": assistant_output or ""})
        except Exception:
            pass
