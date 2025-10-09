import os
import json
from fastapi import APIRouter, HTTPException, Request

from .models import (
    GenerateRequest,
    GenerateResponse,
    PageGenerateRequest,
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
        "Use the provided template as a structure and the user's prompt for specifics.\n"
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
"""

    try:
        completion = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            temperature=0.2,
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

**Content Requirements:**
- Generate content in Editor.js block format as a JSON object with a "blocks" array
- Each block should have: id (unique string), type (header, paragraph, list, table, etc.), and data object
- Use appropriate block types for business content:
  * Headers for sections and subsections (levels 1-4)
  * Paragraphs for detailed explanations
  * Ordered/unordered lists for action items, milestones, and key points
  * Tables for metrics, comparisons, and data presentation
- Structure content with clear hierarchy based on the page type requirements
- Include specific business metrics, KPIs, and measurable outcomes relevant to {page_type}
- Use professional formatting with proper business terminology
- Return only valid JSON with "blocks" array, no markdown or other formatting

**User Request:**
{req.prompt}

**Response Format:**
{{"blocks": [
  {{"id": "unique_id_1", "type": "header", "data": {{"text": "Executive Summary", "level": 2}}}},
  {{"id": "unique_id_2", "type": "paragraph", "data": {{"text": "This project status report provides comprehensive insights into key performance indicators and strategic milestones for the quarter."}}}},
  {{"id": "unique_id_3", "type": "header", "data": {{"text": "Key Performance Indicators", "level": 3}}}},
  {{"id": "unique_id_4", "type": "list", "data": {{"style": "unordered", "items": ["Revenue Growth: 15% increase", "Customer Satisfaction: 92% score", "Project Completion Rate: 85%"]}}}}
]}}
"""

    try:
        completion = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Generate professional business content for this {page_type} page in the specified Editor.js block format. Focus on enterprise business context with KPIs, metrics, project management terminology, and structured reporting. Ensure the content is suitable for business stakeholders and executive decision-making. User request: {req.prompt}"}
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
