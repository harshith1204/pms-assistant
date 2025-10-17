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


def _dedupe_title_in_description(title: str, description: str) -> str:
    """Remove duplicate title from the beginning of the description.

    Handles common cases where models echo the title as a heading or as
    a labeled field (e.g., "Title: <title>"). Also strips underline-style
    markdown headers immediately following the title line (=== or ---).
    """
    try:
        if not title or not description:
            return description or ""

        lines = description.splitlines()

        # Drop leading empty lines
        while lines and not lines[0].strip():
            lines.pop(0)

        if not lines:
            return ""

        # Normalize a candidate line by removing heading markers/bullets
        def normalize(line: str) -> str:
            import re as _re
            line2 = _re.sub(r"^[#>\-\*\s\d\.\)]+", "", line or "").strip()
            # Remove wrapping quotes and trailing punctuation commonly added
            line2 = line2.strip().strip('"\'')
            return line2

        normalized_title = (title or "").strip()
        # Case-insensitive comparison but keep originals
        head = lines[0]

        # Case A: Labeled "Title: ..."
        import re as _re
        m = _re.match(r"(?i)^\s*title\s*:\s*(.+)$", head.strip())
        if m:
            candidate = m.group(1).strip()
            # If a "Description:" line follows, replace the head with its content
            if len(lines) >= 2:
                m2 = _re.match(r"(?i)^\s*description\s*:\s*(.*)$", lines[1].strip())
                if m2:
                    rest = m2.group(1)
                    new_first = rest if rest else ""
                    # Replace first two lines with the remainder
                    new_lines = []
                    if new_first:
                        new_lines.append(new_first)
                    new_lines.extend(lines[2:])
                    lines = new_lines
                else:
                    # Just drop the Title: line
                    lines = lines[1:]
            else:
                # Only title present; drop it
                lines = lines[1:]

            # If model changed the title in labeled form, prefer keeping existing title
            # but remove the echoed title from description regardless

            # Clean any leading underline after removal
            if lines and _re.match(r"^[\-=]{3,}\s*$", lines[0].strip()):
                lines = lines[1:]

            return "\n".join(lines).strip()

        # Case B: Heading line equals the title (with markdown prefixes)
        if normalize(head).lower() == normalized_title.lower():
            lines = lines[1:]
            # Drop underline (=== or ---) immediately following, if present
            if lines and _re.match(r"^[\-=]{3,}\s*$", lines[0].strip()):
                lines = lines[1:]
            return "\n".join(lines).strip()

        return description
    except Exception:
        # On any failure, return original description unmodified
        return description

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

    # Remove duplicate title echoes inside description
    cleaned_description = _dedupe_title_in_description(title.strip(), description.strip())
    return GenerateResponse(title=title.strip(), description=cleaned_description)


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
        "Take the provided title and existing description, and generate a much more detailed and professional description.\n"
        "Add specific details, steps, requirements, and context that would make this work item more actionable for team members.\n"
        "Return markdown in the description with proper formatting, sections, and bullet points.\n"
        "Keep the same title but significantly enhance the description.\n"
        "Respond as JSON only, without code fences or surrounding text.\n"
        "Example response: {\"title\": \"Implement User Authentication\", \"description\": \"## Overview\\nThis task involves implementing...## Requirements\\n- User registration form\\n- Login validation\\n## Steps\\n1. Design database schema...\"}."
    )

    user_prompt = f"""
Current Title:
{req.title}

Current Description:
{req.description}

Instructions:
- Enhance the existing description to be much more detailed and actionable
- Add specific requirements, implementation steps, acceptance criteria
- Include relevant technical details, dependencies, and success metrics
- Structure the description with proper markdown formatting including headers, bullet points, and sections
- Maintain the same title but significantly expand the description
- Produce a JSON object with fields: title, description
- Do not wrap the response in code fences or add explanatory text
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

    # Remove duplicate title echoes inside description
    cleaned_description = _dedupe_title_in_description(title.strip(), description.strip())
    return GenerateResponse(title=title.strip(), description=cleaned_description)


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

