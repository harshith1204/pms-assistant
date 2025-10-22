import os
import json
from fastapi import APIRouter, HTTPException, Request

from .models import (
    GenerateRequest,
    GenerateResponse,
    PageGenerateRequest,
    WorkItemSurpriseMeRequest,
)
from .prompts import (
    PAGE_TYPE_PROMPTS,
    WORK_ITEM_GENERATION_PROMPTS,
    WORK_ITEM_SURPRISE_ME_PROMPTS,
    PAGE_CONTENT_GENERATION_PROMPTS
)

try:
    from groq import Groq  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Groq = None  # type: ignore


router = APIRouter()


def _strip_code_fences(text: str) -> str:
    """Remove simple markdown code fences from a string if present."""
    try:
        s = (text or "").strip()
        if s.startswith("```") and s.endswith("```"):
            # Remove first and last fence; tolerate language tag after opening fence
            s = s[3:]  # drop opening ```
            # Drop optional language identifier (e.g., json)
            while s and s[0] in "\n \tabcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ":
                if s[0] == "\n":
                    s = s[1:]
                    break
                # consume characters until newline (language tag)
                s = s[1:]
            # Remove trailing closing fence
            if s.endswith("```"):
                s = s[:-3]
            return s.strip()
        return s
    except Exception:
        return text


def _try_json_loads(value: str):
    try:
        return json.loads(value)
    except Exception:
        return None


def _unwrap_description(desc_val, fallback: str) -> str:
    """Normalize description value to a plain markdown string.

    Handles cases where the model nests JSON inside the description field
    (e.g., description is a JSON string containing {"title", "description"}).
    """
    # Base case: already a plain string
    if isinstance(desc_val, str):
        s = desc_val.strip()

        # If looks like a JSON object/text block, attempt to parse/unescape
        # 1) Remove code fences if any
        s_no_fence = _strip_code_fences(s)

        # 2) If it's a JSON string (e.g., "{...}") try json.loads
        parsed_once = _try_json_loads(s_no_fence)
        if isinstance(parsed_once, dict):
            inner_desc = parsed_once.get("description")
            if isinstance(inner_desc, str) and inner_desc.strip():
                return inner_desc.strip()
            # If no inner description, fall back to stringified markdown-ish content if present
            return s_no_fence
        if isinstance(parsed_once, str):
            # It was a JSON-encoded string; try a second parse in case it contains an object
            parsed_twice = _try_json_loads(parsed_once)
            if isinstance(parsed_twice, dict) and isinstance(parsed_twice.get("description"), str):
                return parsed_twice["description"].strip()
            if isinstance(parsed_twice, str) and parsed_twice.strip():
                return parsed_twice.strip()
        # Not JSON, return as-is
        return s

    # If dict-like, prefer its 'description' key
    if isinstance(desc_val, dict):
        inner = desc_val.get("description")
        if isinstance(inner, str) and inner.strip():
            return inner.strip()
        # Fallback: no string description; surface nothing rather than dumping JSON
        return fallback

    # If list, join lines
    if isinstance(desc_val, list):
        try:
            parts = [str(x).strip() for x in desc_val if str(x).strip()]
            if parts:
                return "\n".join(parts)
        except Exception:
            pass
        return fallback

    # Unknown type, fallback
    return fallback


def _extract_title_and_description(raw_content: str, fallback_title: str, fallback_description: str) -> tuple[str, str]:
    """Best-effort extract of title and markdown description from model output."""
    content = _strip_code_fences(raw_content or "")

    # Try to locate a JSON object within content
    parsed = None
    try:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(content[start : end + 1])
        else:
            # Try direct full parse (in case content itself is valid JSON)
            parsed = json.loads(content)
    except Exception:
        parsed = None

    title = fallback_title
    description = fallback_description

    if isinstance(parsed, dict):
        # Title: prefer explicit field
        if isinstance(parsed.get("title"), str) and parsed["title"].strip():
            title = parsed["title"].strip()
        # Description: aggressively unwrap any nested JSON
        description = _unwrap_description(parsed.get("description"), fallback_description).strip() or fallback_description
        return title, description

    # Not a JSON object → treat the whole content as description body
    body = (content or "").strip()
    if body:
        # First headline/line becomes title if none
        first_line = body.splitlines()[0].strip()
        if not title and first_line:
            title = first_line[:120]
        description = body

    return title.strip() or fallback_title, description.strip() or fallback_description


@router.post("/generate-work-item", response_model=GenerateResponse)
def generate_work_item(req: GenerateRequest) -> GenerateResponse:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    if Groq is None:
        raise HTTPException(status_code=500, detail="groq package not installed on server")

    client = Groq(api_key=api_key)

    system_prompt = WORK_ITEM_GENERATION_PROMPTS['system_prompt']

    user_prompt = WORK_ITEM_GENERATION_PROMPTS['user_prompt_template'].format(
        template_title=req.template.title,
        template_content=req.template.content,
        prompt=req.prompt
    )

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

    # Robust parse to avoid nested JSON in description
    title, description = _extract_title_and_description(
        raw_content=content,
        fallback_title=req.template.title,
        fallback_description=req.template.content,
    )

    return GenerateResponse(title=title, description=description)


@router.post("/generate-work-item-surprise-me", response_model=GenerateResponse)
def generate_work_item_surprise_me(req: WorkItemSurpriseMeRequest) -> GenerateResponse:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    if Groq is None:
        raise HTTPException(status_code=500, detail="groq package not installed on server")

    client = Groq(api_key=api_key)

    # Decide behavior based on whether a description was provided
    provided_description = (req.description or "").strip()
    if provided_description:
        system_prompt = WORK_ITEM_SURPRISE_ME_PROMPTS['with_description']['system_prompt']
        user_prompt = WORK_ITEM_SURPRISE_ME_PROMPTS['with_description']['user_prompt_template'].format(
            title=req.title,
            description=provided_description
        )
    else:
        system_prompt = WORK_ITEM_SURPRISE_ME_PROMPTS['without_description']['system_prompt']
        user_prompt = WORK_ITEM_SURPRISE_ME_PROMPTS['without_description']['user_prompt_template'].format(
            title=req.title
        )

    try:
        completion = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            temperature=0.2,
            max_tokens=512,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = completion.choices[0].message.content or ""
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Groq API error: {exc}")

    # Robust parse to avoid nested JSON in description
    title, description = _extract_title_and_description(
        raw_content=content,
        fallback_title=req.title,
        fallback_description=provided_description,
    )

    return GenerateResponse(title=title, description=description)


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

    system_prompt = PAGE_CONTENT_GENERATION_PROMPTS['system_prompt_template'].format(
        page_type=page_type,
        page_prompt_dict=page_prompt_dict,
        prompt=req.prompt
    )

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

