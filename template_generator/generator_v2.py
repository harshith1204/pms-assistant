"""
Simplified Template Generator v2
- No complex scenario matching
- Let LLM understand intent naturally  
- Clean, minimal prompts
- Consistent output structure
"""

import json
import re
from typing import Dict, Any, Optional
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

import os
from dotenv import load_dotenv
load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("FATAL: GROQ_API_KEY environment variable not set.")


# Single unified prompt - simple and effective
TEMPLATE_PROMPTS = {
    "work_item": """You create work item templates for project management. Generate a clean, professional template.

Output JSON with these fields:
- id: lowercase-hyphenated identifier (e.g., "api-refactor", "login-bug-fix")
- name: Short descriptive name (2-4 words)
- title: Name with relevant emoji prefix (e.g., "🔧 API Refactor")
- description: One clear sentence explaining the purpose
- priority: "High", "Medium", or "Low" based on context
- content: Markdown with 3-4 relevant sections using ## headers

Keep sections practical and relevant to the actual task. Don't use generic placeholders - write helpful starter content based on what you understand from the request.

Example output structure:
{
  "id": "user-auth-update",
  "name": "User Auth Update", 
  "title": "🔐 User Auth Update",
  "description": "Update authentication flow to support OAuth2 providers.",
  "priority": "High",
  "content": "## Objective\\n- Integrate OAuth2 for Google and GitHub login\\n\\n## Tasks\\n- [ ] Set up OAuth credentials\\n- [ ] Update login UI\\n\\n## Acceptance Criteria\\n- Users can log in with Google/GitHub\\n- Existing sessions remain valid"
}""",

    "page": """You create documentation page templates. Generate a clean, professional template.

Output JSON with these fields:
- id: lowercase-hyphenated identifier
- name: Short descriptive name (2-4 words)
- title: Name with relevant emoji prefix (e.g., "📋 Sprint Review")
- description: One clear sentence explaining the purpose
- priority: "High", "Medium", or "Low"
- content: Markdown with 3-4 relevant sections using ## headers

Write helpful starter content, not just placeholders. Adapt sections to what makes sense for the specific page type.""",

    "cycle": """You create sprint/cycle planning templates. Generate a clean, professional template.

Output JSON with these fields:
- id: lowercase-hyphenated identifier  
- name: Short descriptive name (2-4 words)
- title: Name with relevant emoji prefix (e.g., "🚀 Q1 Sprint")
- description: One clear sentence explaining the cycle focus
- priority: "High", "Medium", or "Low"
- content: Markdown with 3-4 relevant sections using ## headers

Focus on goals, deliverables, and timeline. Keep it actionable.""",

    "module": """You create software module/component documentation templates. Generate a clean, professional template.

Output JSON with these fields:
- id: lowercase-hyphenated identifier
- name: Short descriptive name (2-4 words)  
- title: Name with relevant emoji prefix (e.g., "📦 Auth Module")
- description: One clear sentence explaining the module purpose
- priority: "High", "Medium", or "Low"
- content: Markdown with 3-4 relevant sections using ## headers

Focus on purpose, interfaces, and key behaviors.""",

    "epic": """You create epic/initiative templates for large projects. Generate a clean, professional template.

Output JSON with these fields:
- id: lowercase-hyphenated identifier
- name: Short descriptive name (2-4 words)
- title: Name with relevant emoji prefix (e.g., "🎯 Platform Migration")
- description: One clear sentence explaining the epic vision
- priority: "High", "Medium", or "Low"  
- content: Markdown with 3-4 relevant sections using ## headers

Focus on vision, key milestones, and success criteria. Think strategically."""
}


class TemplateGeneratorV2:
    """Simplified template generator - let the LLM do the heavy lifting."""
    
    def __init__(self):
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=1024,
        )

    async def generate_template(
        self, 
        user_input: str, 
        template_type: str = "work_item"
    ) -> Dict[str, Any]:
        """Generate a template based on user input."""
        
        if not user_input or not user_input.strip():
            return {"error": "Please describe what you need a template for."}
        
        prompt_type = template_type.lower()
        system_prompt = TEMPLATE_PROMPTS.get(prompt_type, TEMPLATE_PROMPTS["work_item"])
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Create a template for: {user_input.strip()}")
        ]
        
        try:
            response = await self.llm.ainvoke(messages)
            content = self._extract_json(response.content)
            template = json.loads(content)
            
            # Minimal validation
            required = {"id", "name", "title", "description", "content", "priority"}
            if not required.issubset(template.keys()):
                return {"error": "Template generation failed. Please try again."}
            
            # Add template type
            template["template_type"] = prompt_type
            
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
