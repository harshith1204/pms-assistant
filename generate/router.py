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
        "If key details are missing, avoid placeholder tokens like 'TBD'. Prefer grounded, high-level suggestions or options. Optionally add a short 'Questions' subsection (max 3) only when essential.\n"
        "Keep within the scope of the user's intent; do not introduce unrelated features or parallel workstreams.\n"
        "Return markdown in the description. Keep the title under 120 characters.\n"
        "Be thoughtfully creative in language and structure while staying factual to the provided context.\n"
        "Respond as JSON only, without code fences or surrounding text.\n"
        "Example response: {\"title\": \"Code Review: Login Flow\", \"description\": \"## Summary\\nReview the login flow for usability, security, and resilience.\\n\\n## Scope\\n- Authentication flows (sign in, sign up, reset)\\n- Error handling and messaging\\n- Accessibility and mobile responsiveness\\n\\n## Recommendations\\n- Consolidate validation logic across forms\\n- Standardize error states and copy\\n- Add instrumentation for drop-off analysis\\n\\n## Questions\\n- Which flows are in scope?\\n- Any compliance constraints (e.g., MFA policy)?\"}."
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
- If information is missing, avoid placeholders. Instead, write grounded, high-level suggestions. Optionally add a brief "Questions" subsection (max 3) when essential.
- Keep scope strictly aligned to the user prompt; avoid adding extra features or work outside the described task.
"""

    try:
        completion = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            temperature=float(os.getenv("GROQ_TEMPERATURE", "0.4")),
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
        "Where specifics are missing, avoid placeholder tokens. Prefer grounded, high-level framing and recommendations. Optionally add a short 'Questions' subsection (max 3) to capture key clarifications.\n"
        "Return markdown in the description with proper formatting, sections, and bullet points.\n"
        "Keep the same title but significantly enhance the structure, clarity, and actionability of the description without expanding scope.\n"
        "Be concise: target 150–220 words total. Use at most 4 sections (e.g., Overview, Requirements, Steps, Acceptance Criteria) plus an optional 'Questions' section.\n"
        "Limit lists to a maximum of 5 bullets per list.\n"
        "Respond as JSON only, without code fences or surrounding text.\n"
        "Example response: {\"title\": \"Implement User Authentication\", \"description\": \"## Overview\\nImplement secure user authentication for the web app.\\n\\n## Requirements\\n- Registration and login flows with input validation\\n- Error states with clear, consistent messaging\\n- Consider MFA readiness and session management\\n\\n## Steps\\n1. Design database entities (users, sessions, tokens)\\n2. Implement API endpoints (register, login, logout)\\n3. Integrate client-side forms and validation\\n\\n## Questions\\n- Preferred auth provider or in-house?\\n- Any specific compliance constraints (e.g., SOC2, GDPR)?\"}."
    )

    user_prompt = f"""
Current Title:
{req.title}

Current Description:
{req.description}

Instructions:
- Enhance the existing description to be more structured, clear, and actionable without adding new scope.
- Add requirements, steps, and acceptance criteria only when supported by the current description; when specifics are missing, avoid placeholders and provide grounded, high-level guidance instead.
- Include dependencies and success measures only if stated; do not invent metrics. Prefer qualitative phrasing over numbers unless provided.
- Structure the description with proper markdown formatting including headers, bullet points, and sections.
- Maintain the same title but improve the description's completeness and readability.
- Be concise: limit the entire description to 220 words maximum.
- Use at most 4 sections (besides an optional "Questions" section). Limit any list to 5 bullets max.
- Produce a JSON object with fields: title, description.
- Do not wrap the response in code fences or add explanatory text.
- Optionally add a "Questions" subsection (max 3) only when essential.
"""

    try:
        completion = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            temperature=float(os.getenv("GROQ_TEMPERATURE", "0.4")),
            max_tokens=350,
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

    # Enforce concise output: trim description to ~220 words if needed
    try:
        words = description.split()
        if len(words) > 220:
            description = " ".join(words[:220]) + " …"
    except Exception:
        # If splitting fails for any reason, fall back to a reasonable character cap
        if len(description) > 2000:
            description = description[:2000] + " …"

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
- Avoid placeholder tokens like "[TBD]". When information is missing, provide grounded, high-level framing and propose options. Optionally include a final "Questions for Stakeholders" section (up to 5) when essential.
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
  {{"id": "unique_id_2", "type": "paragraph", "data": {{"text": "This report summarizes current status and priorities. Metrics will be incorporated once validated."}}}},
  {{"id": "unique_id_3", "type": "header", "data": {{"text": "Key Performance Indicators", "level": 3}}}},
  {{"id": "unique_id_4", "type": "list", "data": {{"style": "unordered", "items": ["Define KPI owners and data sources", "Confirm reporting cadence and thresholds", "Outline current trend direction qualitatively"]}}}},
  {{"id": "unique_id_5", "type": "header", "data": {{"text": "Questions for Stakeholders", "level": 3}}}},
  {{"id": "unique_id_6", "type": "list", "data": {{"style": "unordered", "items": ["Which KPIs are in scope?", "Do we have the latest metrics?", "Any constraints or deadlines to note?"]}}}}
]}}
"""

    try:
        completion = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            temperature=float(os.getenv("GROQ_TEMPERATURE", "0.35")),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Generate professional business content for this {page_type} page in the specified Editor.js block format. Use only information present in the request/context; do not invent metrics or facts. When data is missing, avoid placeholders—offer grounded framing and include a 'Questions for Stakeholders' section at the end when essential. Ensure suitability for business stakeholders and executive decision-making. User request: {req.prompt}"}
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

