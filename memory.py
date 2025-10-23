
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage, SystemMessage
from langchain_core.callbacks import AsyncCallbackHandler
import asyncio
import contextlib
from typing import Dict, Any, List, AsyncGenerator, Optional
from typing import Tuple
import tools
from datetime import datetime
import time
import math
from collections import defaultdict, deque
import os

class ConversationMemory:
    """Manages conversation history for maintaining context"""

    def __init__(self, max_messages_per_conversation: int = 50):
        self.conversations: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_messages_per_conversation))
        self.max_messages_per_conversation = max_messages_per_conversation
        # Rolling summary per conversation (compact)
        self.summaries: Dict[str, str] = {}
        self.turn_counters: Dict[str, int] = defaultdict(int)

    def add_message(self, conversation_id: str, message: BaseMessage):
        """Add a message to the conversation history"""
        self.conversations[conversation_id].append(message)

    def get_conversation_history(self, conversation_id: str) -> List[BaseMessage]:
        """Get the conversation history for a given conversation ID"""
        return list(self.conversations[conversation_id])

    def clear_conversation(self, conversation_id: str):
        """Clear the conversation history for a given conversation ID"""
        if conversation_id in self.conversations:
            self.conversations[conversation_id].clear()

    def get_recent_context(self, conversation_id: str, max_tokens: int = 3000) -> List[BaseMessage]:
        """Get recent conversation context with a token budget and rolling summary."""
        messages = self.get_conversation_history(conversation_id)

        # Approximate token counting (≈4 chars/token)
        def approx_tokens(text: str) -> int:
            try:
                return max(1, math.ceil(len(text) / 4))
            except Exception:
                return len(text) // 4

        budget = max(500, max_tokens)
        used = 0
        selected: List[BaseMessage] = []

        # Walk backwards to select most recent turns under budget
        for msg in reversed(messages):
            content = getattr(msg, "content", "")
            used += approx_tokens(str(content)) + 8
            if used > budget:
                break
            selected.append(msg)

        selected.reverse()

        # Prepend rolling summary if present and within budget
        summary = self.summaries.get(conversation_id)
        if summary:
            stoks = approx_tokens(summary)
            if used + stoks <= budget:
                selected = [SystemMessage(content=f"Conversation summary (condensed):\n{summary}")] + selected

        return selected

    def register_turn(self, conversation_id: str) -> None:
        self.turn_counters[conversation_id] += 1

    def should_update_summary(self, conversation_id: str, every_n_turns: int = 3) -> bool:
        return self.turn_counters[conversation_id] % every_n_turns == 0

    async def update_summary_async(self, conversation_id: str, llm_for_summary) -> None:
        """Update the rolling summary asynchronously to avoid latency in main path."""
        try:
            history = self.get_conversation_history(conversation_id)
            if not history:
                return
            recent = history[-12:]
            prompt = [
                SystemMessage(content=(
                    "Summarize the durable facts, goals, and decisions from the conversation. "
                    "Keep it 6-10 bullets, under 600 tokens. Avoid chit-chat."
                ))
            ] + recent + [HumanMessage(content="Produce condensed summary now.")]
            resp = await llm_for_summary.ainvoke(prompt)
            if getattr(resp, "content", None):
                self.summaries[conversation_id] = str(resp.content)
        except Exception:
            # Best-effort; ignore failures
            pass

# Global conversation memory instance
conversation_memory = ConversationMemory()
