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

groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("FATAL: GROQ_API_KEY environment variable not set.")

System_prompt = (
"Instruction:\n"
"You are an expert in structured task design and workflow organization. "
"Based on the user's description of their role, domain, or type of task, "
"generate a single task template in valid JSON format.\n\n"

"Rules:\n"
"- Infer the domain, purpose, and urgency from the user's input.\n"
"- Output **only** valid JSON — no explanations, notes, or extra text.\n"
"- Every template must include the fields exactly as shown: id, name, description, title, content, priority.\n"
"- Use concise, domain-relevant section headings (4–6) in the 'content' field, formatted in Markdown (## Heading).\n"
"- Choose a relevant emoji for the 'title' field and include a clear placeholder (e.g., [Task Name]).\n"
"- Assign 'priority' as 'High', 'Medium', or 'Low' based on task urgency implied by the input.\n"
"- Ensure 'id' is lowercase, unique, and hyphen-separated (e.g., 'data-analysis-task').\n"
"- Avoid repeating examples or including any commentary outside the JSON output.\n"
"- If the input lacks sufficient context to infer a domain or task type, return:\n"
"{\"error\": \"Insufficient context. Please describe your role or task type.\"}\n\n"

"Output Format Example:\n"
"{\n"
"  \"id\": \"marketing-campaign\",\n"
"  \"name\": \"Marketing Campaign\",\n"
"  \"description\": \"Template for planning and tracking marketing campaigns.\",\n"
"  \"title\": \"📢 Campaign: [Campaign Name]\",\n"
"  \"content\": \"## Objective\\n\\n## Target Audience\\n\\n## Key Channels\\n\\n## Metrics\\n\\n## Timeline\\n\",\n"
"  \"priority\": \"Medium\"\n"
"}"
)

class TemplateGenerator:
    def __init__ (self, system_prompt: str = System_prompt):
        self.llm = ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=0.1,  # Slightly creative for query understanding
            max_tokens=1024,
            top_p=0.8,
        )
        self.system_prompt = system_prompt
    
    async def generate_template(self, user_input: str) -> Dict[str, Any]:
        messages = [
            SystemMessage(content=self.system_prompt),
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
    
