import os
import json
from fastapi import APIRouter, HTTPException, Request

# Helpers to robustly parse model output that sometimes double-encodes JSON
def _unwrap_description(candidate):
    """Return a clean markdown description string.

    Some model responses incorrectly place a JSON object as a string inside the
    description, e.g. "{\"title\":\"X\",\"description\":\"...\"}".
    This function detects and unwraps such cases to return only the inner
    description text.
    """
    # If already a dict, prefer its 'description' field
    if isinstance(candidate, dict):
        inner = candidate.get("description")
        if isinstance(inner, str) and inner.strip():
            return inner.strip()
        # Fallback to common alternative keys
        for key in ("content", "body", "text"):
            inner_alt = candidate.get(key)
            if isinstance(inner_alt, str) and inner_alt.strip():
                return inner_alt.strip()
        # Last resort: stringify the dict
        return json.dumps(candidate, ensure_ascii=False)

    # Coerce non-strings
    if not isinstance(candidate, str):
        return str(candidate)

    s = candidate.strip()
    # Fast-path: nothing that looks like JSON
    if not (s.startswith("{") and s.endswith("}")):
        return s

    # Attempt to parse nested JSON string
    try:
        nested = json.loads(s)
        if isinstance(nested, dict):
            inner = nested.get("description")
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
            for key in ("content", "body", "text"):
                inner_alt = nested.get(key)
                if isinstance(inner_alt, str) and inner_alt.strip():
                    return inner_alt.strip()
    except Exception:
        # If parsing fails, return the original string
        return s

    # If no usable field found, return original
    return s

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

    # Normalize description to avoid double-encoded JSON structures
    description = _unwrap_description(description)

    return GenerateResponse(title=title.strip(), description=description.strip())


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

    # Best-effort parse: if JSON-like present, extract; else use raw content
    title = req.title
    description = provided_description
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

    # Normalize description to avoid double-encoded JSON structures
    description = _unwrap_description(description)

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

