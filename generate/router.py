import os
import json
from fastapi import APIRouter, HTTPException, Request

from .models import (
    GenerateRequest,
    GenerateResponse,
    PageGenerateRequest,
    WorkItemSurpriseMeRequest,
)
from .prompts import PAGE_TYPE_PROMPTS

try:
    from groq import Groq  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Groq = None  # type: ignore


router = APIRouter()


@router.post("/generate-work-item", response_model=GenerateResponse)
def generate_work_item(req: GenerateRequest) -> GenerateResponse:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    if Groq is None:
        raise HTTPException(status_code=500, detail="groq package not installed on server")

    client = Groq(api_key=api_key)

    system_prompt = (
        "You are an assistant that generates concise, actionable work item titles and descriptions.\n"
        "Use ONLY the information explicitly provided by the user prompt and template; do NOT invent or infer facts, metrics, names, dates, or commitments.\n"
        "If key details are missing, keep language neutral (e.g., 'TBD') and add a 'Questions' subsection inside the description with up to 5 clarifying questions.\n"
        "Keep within the scope of the user's intent; do not introduce unrelated features or parallel workstreams.\n"
        "Return markdown in the description. Keep the title under 120 characters.\n"
        "Respond as JSON only, without code fences or surrounding text.\n"
        "Example response: {\"title\": \"Code Review: Login Flow\", \"description\": \"## Summary\\nReview the login flow...\"}."
    )

    user_prompt = f"""
Template Title:
{req.template.title}

Template Content:
{req.template.content}

User Prompt:
{req.prompt}

Instructions:
- Produce a JSON object with fields: title, description.
- Title: one line, no surrounding quotes.
- Description: markdown body with headings/bullets as needed.
- Example: {{"title": "Code Review: Login Flow", "description": "## Summary\nReview the login flow..."}}
- Do not wrap the response in code fences or add explanatory text.
- Only use details provided in the Template Content or User Prompt; do not fabricate requirements, owners, timelines, estimates, or metrics.
- If information is missing, write neutral placeholders like "TBD" and include a "Questions" subsection listing clarifications needed to proceed.
- Keep scope strictly aligned to the user prompt; avoid adding extra features or work outside the described task.
"""

    try:
        completion = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = completion.choices[0].message.content or ""
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Groq API error: {exc}")

    # Best-effort parse: if JSON-like present, extract; else use raw content
    title = req.template.title
    description = req.template.content
    parsed = None
    try:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(content[start : end + 1])
    except Exception:
        parsed = None

    if isinstance(parsed, dict):
        title = parsed.get("title") or title
        description = parsed.get("description") or description
    else:
        description = content.strip() or description
        first_line = description.splitlines()[0] if description else req.prompt
        title = first_line[:120]

    return GenerateResponse(title=title.strip(), description=description.strip())


@router.post("/generate-work-item-surprise-me", response_model=GenerateResponse)
def generate_work_item_surprise_me(req: WorkItemSurpriseMeRequest) -> GenerateResponse:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    if Groq is None:
        raise HTTPException(status_code=500, detail="groq package not installed on server")

    client = Groq(api_key=api_key)

    system_prompt = (
        "You are an assistant that enhances work item descriptions to be more detailed, actionable, and comprehensive.\n"
        "Never invent facts, metrics, owners, dates, or scope; use ONLY what is present in the title and current description.\n"
        "Where specifics are missing, keep language neutral with placeholders like 'TBD' and add a 'Questions' subsection to capture clarifications rather than assuming.\n"
        "Return markdown in the description with proper formatting, sections, and bullet points.\n"
        "Keep the same title but significantly enhance the structure, clarity, and actionability of the description without expanding scope.\n"
        "Respond as JSON only, without code fences or surrounding text.\n"
        "Example response: {\"title\": \"Implement User Authentication\", \"description\": \"## Overview\\nThis task involves implementing user authentication.\\n\\n## Requirements\\n- Registration flow [TBD compliance requirements]\\n- Login validation [TBD error states]\\n\\n## Steps\\n1. Design database schema [TBD fields]\\n2. Implement API endpoints [TBD auth method]\\n\\n## Questions\\n- What auth provider is preferred?\\n- Any SSO requirements?\"}."
    )

    user_prompt = f"""
Current Title:
{req.title}

Current Description:
{req.description}

Instructions:
- Enhance the existing description to be more structured, clear, and actionable without adding new scope.
- Add requirements, steps, and acceptance criteria only when supported by the current description; otherwise use neutral placeholders like "TBD".
- Include dependencies and success measures only if stated; do not invent metrics. Prefer qualitative phrasing over numbers unless provided.
- Structure the description with proper markdown formatting including headers, bullet points, and sections.
- Maintain the same title but improve the description's completeness and readability.
- Produce a JSON object with fields: title, description.
- Do not wrap the response in code fences or add explanatory text.
- Add a "Questions" subsection to surface up to 5 clarifications where information is missing.
"""

    try:
        completion = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = completion.choices[0].message.content or ""
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Groq API error: {exc}")

    # Best-effort parse: if JSON-like present, extract; else use raw content
    title = req.title
    description = req.description
    parsed = None
    try:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(content[start : end + 1])
    except Exception:
        parsed = None

    if isinstance(parsed, dict):
        title = parsed.get("title") or title
        description = parsed.get("description") or description
    else:
        description = content.strip() or description

    return GenerateResponse(title=title.strip(), description=description.strip())


@router.options("/stream-page-content")
async def options_page_content():
    return {"message": "OK"}


@router.get("/stream-page-content")
async def generate_page_content(request: Request):
    try:
        data_param = request.query_params.get("data")
        if not data_param:
            raise HTTPException(status_code=400, detail="No data parameter provided")

        data = json.loads(data_param)
        req = PageGenerateRequest(**data)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request data: {e}")

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    if Groq is None:
        raise HTTPException(status_code=500, detail="groq package not installed on server")

    client = Groq(api_key=api_key)

    context = req.context
    page_type = context.page.get('type', 'DOCUMENTATION')

    page_prompt_dict = PAGE_TYPE_PROMPTS.get(page_type, PAGE_TYPE_PROMPTS['DOCUMENTATION'])

    system_prompt = f"""
You are an AI assistant specialized in generating professional business content for enterprise project management pages in Editor.js block format.

**Business Context:**
- Organization Type: Enterprise Business Environment
- Page Type: {page_type}

{page_prompt_dict}

**Grounding & Safety Rules:**
- Use ONLY facts present in the User Request or Context; do not fabricate names, dates, metrics, financials, or commitments.
- If information is missing, use neutral placeholders like "[TBD]" or bracketed labels, and add a final "Questions for Stakeholders" section with up to 5 clarifications.
- Keep scope tightly aligned to the page type and request; do not introduce unrelated initiatives or assumptions.

**Content Requirements:**
- Generate content in Editor.js block format as a JSON object with a "blocks" array
- Each block should have: id (unique string), type (header, paragraph, list, table, etc.), and data object
- Use appropriate block types for business content:
  * Headers for sections and subsections (levels 1-4)
  * Paragraphs for detailed explanations
  * Ordered/unordered lists for action items, milestones, and key points
  * Tables for metrics, comparisons, and data presentation (only when the data is provided; otherwise use placeholders without numbers)
- Structure content with clear hierarchy based on the page type requirements
- Use professional formatting with proper business terminology
- Return only valid JSON with "blocks" array, no markdown or other formatting

**User Request:**
{req.prompt}

**Response Format:**
{{"blocks": [
  {{"id": "unique_id_1", "type": "header", "data": {{"text": "Executive Summary", "level": 2}}}},
  {{"id": "unique_id_2", "type": "paragraph", "data": {{"text": "This report summarizes current status and priorities. Key figures are [TBD] pending confirmation."}}}},
  {{"id": "unique_id_3", "type": "header", "data": {{"text": "Key Performance Indicators", "level": 3}}}},
  {{"id": "unique_id_4", "type": "list", "data": {{"style": "unordered", "items": ["Revenue Growth: [TBD]", "Customer Satisfaction: [TBD]", "Project Completion Rate: [TBD]"]}}}},
  {{"id": "unique_id_5", "type": "header", "data": {{"text": "Questions for Stakeholders", "level": 3}}}},
  {{"id": "unique_id_6", "type": "list", "data": {{"style": "unordered", "items": ["Which KPIs are in scope?", "Do we have the latest metrics?", "Any constraints or deadlines to note?"]}}}}
]}}
"""

    try:
        completion = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Generate professional business content for this {page_type} page in the specified Editor.js block format. Use only information present in the request/context; do not invent metrics or facts. Where data is missing, use '[TBD]' placeholders and include a 'Questions for Stakeholders' section at the end. Ensure suitability for business stakeholders and executive decision-making. User request: {req.prompt}"}
            ],
            stream=False
        )

        content = completion.choices[0].message.content or "{}"

        try:
            parsed_response = json.loads(content)
            if "blocks" in parsed_response and isinstance(parsed_response["blocks"], list):
                return parsed_response
            else:
                return {
                    "blocks": [
                        {
                            "id": "fallback_1",
                            "type": "paragraph",
                            "data": {"text": content.strip() or "Content generation failed"}
                        }
                    ]
                }
        except json.JSONDecodeError:
            return {
                "blocks": [
                    {
                        "id": "fallback_1",
                        "type": "paragraph",
                        "data": {"text": content.strip() or "Content generation failed"}
                    }
                ]
            }

    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Groq API error: {e}")

