"""
Simplified Template Generator
- Clean, minimal prompts that let the LLM understand intent naturally
- No complex scenario matching or keyword detection
- Consistent output structure across all template types
"""

import json
import re
from typing import Dict, Any
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

import os
from dotenv import load_dotenv
load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("FATAL: GROQ_API_KEY environment variable not set.")


# Clean, focused prompts for each template type
TEMPLATE_PROMPTS = {
    "work_item": """You create work item templates for project management. Generate a clean, professional template based on the user's request.

Output a JSON object with these fields:
- id: lowercase-hyphenated identifier (e.g., "api-refactor", "login-bug-fix")
- name: Short descriptive name (2-4 words)
- title: Name with relevant emoji prefix (e.g., "🔧 API Refactor")
- description: One clear sentence explaining the template's purpose
- priority: "High", "Medium", or "Low" based on apparent urgency
- content: Markdown with 3-4 relevant sections using ## headers

Guidelines:
- Keep sections practical and relevant to the actual task
- Write helpful starter content, not just "TODO" placeholders
- Adapt structure to what makes sense for the specific work item
- Use checkboxes [ ] for actionable items

Example output:
{
  "id": "user-auth-update",
  "name": "User Auth Update",
  "title": "🔐 User Auth Update",
  "description": "Template for updating authentication flows and security features.",
  "priority": "High",
  "content": "## Objective\\nDescribe the authentication change and its business value.\\n\\n## Tasks\\n- [ ] Core implementation task\\n- [ ] Update tests\\n- [ ] Update documentation\\n\\n## Acceptance Criteria\\n- [ ] Feature works as specified\\n- [ ] Security review passed"
}""",

    "page": """You create documentation page templates. Generate a clean, professional template based on the user's request.

Output a JSON object with these fields:
- id: lowercase-hyphenated identifier
- name: Short descriptive name (2-4 words)
- title: Name with relevant emoji prefix (e.g., "📋 Sprint Review")
- description: One clear sentence explaining the template's purpose
- priority: "High", "Medium", or "Low"
- content: Markdown with 3-4 relevant sections using ## headers

Guidelines:
- Write helpful starter content that guides the user
- Adapt sections to what makes sense for the specific page type
- Include practical examples where helpful
- Use tables for structured data when appropriate""",

    "cycle": """You create sprint/cycle planning templates. Generate a clean, professional template based on the user's request.

Output a JSON object with these fields:
- id: lowercase-hyphenated identifier
- name: Short descriptive name (2-4 words)
- title: Name with relevant emoji prefix (e.g., "🚀 Q1 Sprint")
- description: One clear sentence explaining the cycle's focus
- priority: "High", "Medium", or "Low"
- content: Markdown with 3-4 relevant sections using ## headers

Guidelines:
- Focus on goals, deliverables, and timeline
- Keep it actionable and measurable
- Include capacity and risk considerations""",

    "module": """You create software module/component documentation templates. Generate a clean, professional template based on the user's request.

Output a JSON object with these fields:
- id: lowercase-hyphenated identifier
- name: Short descriptive name (2-4 words)
- title: Name with relevant emoji prefix (e.g., "📦 Auth Module")
- description: One clear sentence explaining the module's purpose
- priority: "High", "Medium", or "Low"
- content: Markdown with 3-4 relevant sections using ## headers

Guidelines:
- Focus on purpose, interfaces, and key behaviors
- Include dependency information
- Document integration points""",

    "epic": """You create epic/initiative templates for large projects. Generate a clean, professional template based on the user's request.

Output a JSON object with these fields:
- id: lowercase-hyphenated identifier
- name: Short descriptive name (2-4 words)
- title: Name with relevant emoji prefix (e.g., "🎯 Platform Migration")
- description: One clear sentence explaining the epic's vision
- priority: "High", "Medium", or "Low"
- content: Markdown with 3-4 relevant sections using ## headers

Guidelines:
- Focus on vision, key milestones, and success criteria
- Think strategically about scope and phasing
- Include measurable outcomes"""
}


class TemplateGenerator:
    """Simplified template generator that lets the LLM do the heavy lifting."""

    def __init__(self):
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=1024,
        )

    async def generate_template(
        self,
        user_input: str,
        prompt_type: str = "work_item"
    ) -> Dict[str, Any]:
        """Generate a template based on user input."""

        if not user_input or not user_input.strip():
            return {"error": "Please describe what you need a template for."}

        template_type = prompt_type.lower()
        system_prompt = TEMPLATE_PROMPTS.get(template_type, TEMPLATE_PROMPTS["work_item"])

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Create a template for: {user_input.strip()}")
        ]

        try:
            response = await self.llm.ainvoke(messages)
            content = self._extract_json(response.content)
            template = json.loads(content)

            # Validate required fields
            required = {"id", "name", "title", "description", "content", "priority"}
            if not required.issubset(template.keys()):
                return {"error": "Template generation failed. Please try again."}

            # Add template type
            template["template_type"] = template_type

            # Ensure priority is valid
            if template.get("priority") not in {"High", "Medium", "Low"}:
                template["priority"] = "Medium"

            return template

        except json.JSONDecodeError:
            return {"error": "Failed to generate template. Please try again."}
        except Exception as e:
            return {"error": f"Generation error: {str(e)}"}

    def _extract_json(self, content: str) -> str:
        """Extract JSON from LLM response."""
        if not content:
            return "{}"

        text = content.strip()

        # Remove thinking tags if present
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

        # Extract from code blocks
        if "```" in text:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if match:
                text = match.group(1).strip()

        # Find JSON object
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            text = text[start:end]

        return text
