import json
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from bson import ObjectId
from bson.binary import Binary
from pydantic import BaseModel

import os
from dotenv import load_dotenv
load_dotenv()

from .prompts import (
    WORK_ITEM_TEMPLATE_PROMPT,
    PAGE_TEMPLATE_PROMPT,
    CYCLE_TEMPLATE_PROMPT,
    MODULE_TEMPLATE_PROMPT,
    EPIC_TEMPLATE_PROMPT
)

groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("FATAL: GROQ_API_KEY environment variable not set.")

def get_prompt_for_type(prompt_type: str) -> str:
    """Get the appropriate prompt based on template type."""
    prompt_mapping = {
        "work_item": WORK_ITEM_TEMPLATE_PROMPT,
        "page": PAGE_TEMPLATE_PROMPT,
        "cycle": CYCLE_TEMPLATE_PROMPT,
        "module": MODULE_TEMPLATE_PROMPT,
        "epic": EPIC_TEMPLATE_PROMPT,
    }

    # Default to work_item if type not found
    return prompt_mapping.get(prompt_type.lower(), WORK_ITEM_TEMPLATE_PROMPT)

class TemplateGenerator:
    def __init__ (self):
        self.llm = ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=0.1,  # Slightly creative for query understanding
            max_tokens=1024,
            top_p=0.8,
        )

    async def generate_template(self, user_input: str, prompt_type: str = "work_item") -> Dict[str, Any]:
        system_prompt = get_prompt_for_type(prompt_type)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_input)
        ]
        ai_response = await self.llm.ainvoke(messages)
        content = self._clean_model_output(ai_response.content)
        
        # Attempt to parse the response as JSON
        try:
            template = json.loads(content)
            required_keys = {"id", "name", "description", "title", "content", "priority"}
            if not required_keys.issubset(template.keys()):
                return {"error": "Missing required fields in template output."}
            return template
        except json.JSONDecodeError:
            return {"error": "Failed to parse template. Invalid JSON format."}

    def _clean_model_output(self, content: Optional[str]) -> str:
        if not content:
            return ""
        text = content.strip()
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        text = re.sub(r"<think>.*", "", text, flags=re.DOTALL)
        if text.startswith("```"):
            stripped = text.strip("`\n")
            if stripped.startswith("json\n"):
                stripped = stripped[5:]
            text = stripped
        return text.strip()
    
