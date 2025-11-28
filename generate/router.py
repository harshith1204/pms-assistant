import os
import re
import json
import asyncio
import logging
from fastapi import APIRouter, HTTPException

from .models import (
    GenerateRequest,
    GenerateResponse,
    PageGenerateResponse,
    UserStoryResponse,
    UserStorySurpriseMeRequest,
    ProjectResponse,
    FeatureResponse,
    Requirement,
    WorkItemSurpriseMeRequest,
    CycleSurpriseMeRequest,
    ModuleSurpriseMeRequest,
    EpicSurpriseMeRequest,
)
from .prompts import (
    WORK_ITEM_GENERATION_PROMPTS,
    WORK_ITEM_SURPRISE_ME_PROMPTS,
    PAGE_GENERATION_PROMPTS,
    CYCLE_GENERATION_PROMPTS,
    CYCLE_SURPRISE_ME_PROMPTS,
    MODULE_GENERATION_PROMPTS,
    MODULE_SURPRISE_ME_PROMPTS,
    EPIC_GENERATION_PROMPTS,
    EPIC_SURPRISE_ME_PROMPTS,
    USER_STORY_GENERATION_PROMPTS,
    USER_STORY_SURPRISE_ME_PROMPTS,
    FEATURE_GENERATION_PROMPTS,
    PROJECT_GENERATION_PROMPTS,
)

try:
    from groq import Groq  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Groq = None  # type: ignore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generate", tags=["generate"])

# Helper function to call Groq API with timeout
async def call_groq_with_timeout(client, model, temperature, messages, max_tokens=None, timeout=30.0):
    """Call Groq API in executor with timeout protection."""
    loop = asyncio.get_event_loop()
    
    def _call_groq():
        kwargs = {
            "model": model,
            "temperature": temperature,
            "messages": messages,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        return client.chat.completions.create(**kwargs)
    
    try:
        completion = await asyncio.wait_for(
            loop.run_in_executor(None, _call_groq),
            timeout=timeout
        )
        return completion
    except asyncio.TimeoutError:
        logger.error(f"Groq API call timed out after {timeout} seconds")
        raise HTTPException(status_code=504, detail=f"Groq API request timed out after {timeout} seconds")
    except Exception as exc:
        logger.error(f"Groq API error: {exc}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Groq API error: {str(exc)}")


@router.post("/work-item", response_model=GenerateResponse)
async def generate_work_item(req: GenerateRequest) -> GenerateResponse:
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

    completion = await call_groq_with_timeout(
        client=client,
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        temperature=0.4,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    content = completion.choices[0].message.content or ""

    # Best-effort parse: if JSON-like present, extract; else use raw content
    title = req.template.title
    description = req.template.content
    parsed = None
    try:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(content[start : end + 1])
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON from Groq response: {e}. Content preview: {content[:200]}")
        parsed = None

    if isinstance(parsed, dict):
        title = parsed.get("title") or title
        description = parsed.get("description") or description
    else:
        # If we got content but couldn't parse, use it as description
        if content.strip():
            description = content.strip()
            first_line = description.splitlines()[0] if description else req.prompt
            title = first_line[:120] if len(first_line) > 120 else first_line
        else:
            # No content from API, use template defaults
            description = req.template.content
            title = req.template.title

    return GenerateResponse(title=title.strip(), description=description.strip())


@router.post("/work-item-surprise-me", response_model=GenerateResponse)
async def generate_work_item_surprise_me(req: WorkItemSurpriseMeRequest) -> GenerateResponse:
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

    completion = await call_groq_with_timeout(
        client=client,
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        temperature=0.4,
        max_tokens=512,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    # The model is instructed to return ONLY markdown description
    generated_description = (completion.choices[0].message.content or "").strip()

    # Always return the original title and the generated markdown description
    return GenerateResponse(title=(req.title or "").strip(), description=generated_description)


def extract_json_from_response(content: str) -> str:
    """Extract JSON from LLM response, handling code fences and other wrappers."""
    # Try to find JSON in code fences first (```json ... ``` or ``` ... ```)
    code_fence_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    matches = re.findall(code_fence_pattern, content)
    if matches:
        # Use the first match that looks like JSON
        for match in matches:
            if match.strip().startswith('{'):
                content = match.strip()
                break
    
    # Find the outermost JSON object
    start = content.find("{")
    if start == -1:
        return ""
    
    # Count braces to find the matching closing brace
    brace_count = 0
    end = start
    for i, char in enumerate(content[start:], start):
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                end = i + 1
                break
    
    return content[start:end] if end > start else ""


def validate_editor_block(block: dict, index: int) -> dict:
    """Validate and normalize an Editor.js block."""
    if not isinstance(block, dict):
        return None
    
    block_type = block.get("type")
    data = block.get("data")
    
    if not block_type or not isinstance(data, dict):
        return None
    
    # Ensure block has an ID
    block_id = block.get("id") or f"blk_{index + 1}"
    
    # Normalize common block types
    normalized = {
        "id": block_id,
        "type": block_type,
        "data": data
    }
    
    return normalized


@router.post("/page", response_model=PageGenerateResponse)
async def generate_page(req: GenerateRequest) -> PageGenerateResponse:
    """Generate page content in Editor.js blocks format."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    if Groq is None:
        raise HTTPException(status_code=500, detail="groq package not installed on server")

    client = Groq(api_key=api_key)

    system_prompt = PAGE_GENERATION_PROMPTS['system_prompt']

    user_prompt = PAGE_GENERATION_PROMPTS['user_prompt_template'].format(
        template_title=req.template.title,
        template_content=req.template.content,
        prompt=req.prompt
    )

    completion = await call_groq_with_timeout(
        client=client,
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        temperature=0.4,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    content = completion.choices[0].message.content or ""

    # Parse JSON response with Editor.js blocks
    title = req.template.title
    blocks = []
    
    try:
        # Extract JSON from response (handles code fences, nested braces, etc.)
        json_str = extract_json_from_response(content)
        
        if json_str:
            parsed = json.loads(json_str)
            
            if isinstance(parsed, dict):
                title = parsed.get("title") or title
                raw_blocks = parsed.get("blocks", [])
                
                # Validate and clean blocks
                if isinstance(raw_blocks, list):
                    for i, block in enumerate(raw_blocks):
                        validated = validate_editor_block(block, i)
                        if validated:
                            blocks.append(validated)
                            
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON from Groq response: {e}. Content preview: {content[:300]}")
    except Exception as e:
        logger.warning(f"Error processing page response: {e}. Content preview: {content[:300]}")

    # Fallback: if no valid blocks, create structured content from raw response
    if not blocks:
        # Try to create meaningful content from the raw response
        fallback_text = content.strip() if content.strip() else "Content generation in progress. Please add your content here."
        
        # Clean up any JSON artifacts from fallback text
        if fallback_text.startswith('{') or fallback_text.startswith('```'):
            fallback_text = "Content generation in progress. Please add your content here."
        
        blocks = [
            {
                "id": "blk_1",
                "type": "header",
                "data": {"text": title, "level": 2}
            },
            {
                "id": "blk_2", 
                "type": "paragraph",
                "data": {"text": fallback_text}
            }
        ]

    return PageGenerateResponse(title=title.strip(), blocks=blocks)


@router.post("/cycle", response_model=GenerateResponse)
async def generate_cycle(req: GenerateRequest) -> GenerateResponse:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    if Groq is None:
        raise HTTPException(status_code=500, detail="groq package not installed on server")

    client = Groq(api_key=api_key)

    system_prompt = CYCLE_GENERATION_PROMPTS['system_prompt']

    user_prompt = CYCLE_GENERATION_PROMPTS['user_prompt_template'].format(
        template_title=req.template.title,
        template_content=req.template.content,
        prompt=req.prompt
    )

    completion = await call_groq_with_timeout(
        client=client,
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        temperature=0.4,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    content = completion.choices[0].message.content or ""

    # Parse JSON response
    title = req.template.title
    description = req.template.content
    parsed = None
    try:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(content[start : end + 1])
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON from Groq response: {e}. Content preview: {content[:200]}")
        parsed = None

    if isinstance(parsed, dict):
        title = parsed.get("title") or title
        description = parsed.get("description") or description
    else:
        if content.strip():
            description = content.strip()
            first_line = description.splitlines()[0] if description else req.prompt
            title = first_line[:120] if len(first_line) > 120 else first_line
        else:
            description = req.template.content
            title = req.template.title

    return GenerateResponse(title=title.strip(), description=description.strip())


@router.post("/cycle-surprise-me", response_model=GenerateResponse)
async def generate_cycle_surprise_me(req: CycleSurpriseMeRequest) -> GenerateResponse:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    if Groq is None:
        raise HTTPException(status_code=500, detail="groq package not installed on server")

    client = Groq(api_key=api_key)

    # Decide behavior based on whether a description was provided
    provided_description = (req.description or "").strip()
    if provided_description:
        system_prompt = CYCLE_SURPRISE_ME_PROMPTS['with_description']['system_prompt']
        user_prompt = CYCLE_SURPRISE_ME_PROMPTS['with_description']['user_prompt_template'].format(
            title=req.title,
            description=provided_description
        )
    else:
        system_prompt = CYCLE_SURPRISE_ME_PROMPTS['without_description']['system_prompt']
        user_prompt = CYCLE_SURPRISE_ME_PROMPTS['without_description']['user_prompt_template'].format(
            title=req.title
        )

    completion = await call_groq_with_timeout(
        client=client,
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        temperature=0.4,
        max_tokens=512,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    generated_description = (completion.choices[0].message.content or "").strip()

    return GenerateResponse(title=(req.title or "").strip(), description=generated_description)


@router.post("/epic", response_model=GenerateResponse)
async def generate_epic(req: GenerateRequest) -> GenerateResponse:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    if Groq is None:
        raise HTTPException(status_code=500, detail="groq package not installed on server")

    client = Groq(api_key=api_key)

    system_prompt = EPIC_GENERATION_PROMPTS['system_prompt']

    user_prompt = EPIC_GENERATION_PROMPTS['user_prompt_template'].format(
        template_title=req.template.title,
        template_content=req.template.content,
        prompt=req.prompt
    )

    completion = await call_groq_with_timeout(
        client=client,
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        temperature=0.4,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    content = completion.choices[0].message.content or ""

    title = req.template.title
    description = req.template.content
    parsed = None
    try:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(content[start: end + 1])
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON from Groq response: {e}. Content preview: {content[:200]}")
        parsed = None

    if isinstance(parsed, dict):
        title = parsed.get("title") or title
        description = parsed.get("description") or description
    else:
        if content.strip():
            description = content.strip()
            first_line = description.splitlines()[0] if description else req.prompt
            title = first_line[:120] if len(first_line) > 120 else first_line
        else:
            description = req.template.content
            title = req.template.title

    return GenerateResponse(title=title.strip(), description=description.strip())


@router.post("/epic-surprise-me", response_model=GenerateResponse)
async def generate_epic_surprise_me(req: EpicSurpriseMeRequest) -> GenerateResponse:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    if Groq is None:
        raise HTTPException(status_code=500, detail="groq package not installed on server")

    client = Groq(api_key=api_key)

    provided_description = (req.description or "").strip()
    if provided_description:
        system_prompt = EPIC_SURPRISE_ME_PROMPTS['with_description']['system_prompt']
        user_prompt = EPIC_SURPRISE_ME_PROMPTS['with_description']['user_prompt_template'].format(
            title=req.title,
            description=provided_description
        )
    else:
        system_prompt = EPIC_SURPRISE_ME_PROMPTS['without_description']['system_prompt']
        user_prompt = EPIC_SURPRISE_ME_PROMPTS['without_description']['user_prompt_template'].format(
            title=req.title
        )

    completion = await call_groq_with_timeout(
        client=client,
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        temperature=0.4,
        max_tokens=512,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    generated_description = (completion.choices[0].message.content or "").strip()

    return GenerateResponse(title=(req.title or "").strip(), description=generated_description)

@router.post("/module", response_model=GenerateResponse)
async def generate_module(req: GenerateRequest) -> GenerateResponse:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    if Groq is None:
        raise HTTPException(status_code=500, detail="groq package not installed on server")

    client = Groq(api_key=api_key)

    system_prompt = MODULE_GENERATION_PROMPTS['system_prompt']

    user_prompt = MODULE_GENERATION_PROMPTS['user_prompt_template'].format(
        template_title=req.template.title,
        template_content=req.template.content,
        prompt=req.prompt
    )

    completion = await call_groq_with_timeout(
        client=client,
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        temperature=0.4,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    content = completion.choices[0].message.content or ""

    # Parse JSON response
    title = req.template.title
    description = req.template.content
    parsed = None
    try:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(content[start : end + 1])
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON from Groq response: {e}. Content preview: {content[:200]}")
        parsed = None

    if isinstance(parsed, dict):
        title = parsed.get("title") or title
        description = parsed.get("description") or description
    else:
        if content.strip():
            description = content.strip()
            first_line = description.splitlines()[0] if description else req.prompt
            title = first_line[:120] if len(first_line) > 120 else first_line
        else:
            description = req.template.content
            title = req.template.title

    return GenerateResponse(title=title.strip(), description=description.strip())


@router.post("/module-surprise-me", response_model=GenerateResponse)
async def generate_module_surprise_me(req: ModuleSurpriseMeRequest) -> GenerateResponse:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    if Groq is None:
        raise HTTPException(status_code=500, detail="groq package not installed on server")

    client = Groq(api_key=api_key)

    # Decide behavior based on whether a description was provided
    provided_description = (req.description or "").strip()
    if provided_description:
        system_prompt = MODULE_SURPRISE_ME_PROMPTS['with_description']['system_prompt']
        user_prompt = MODULE_SURPRISE_ME_PROMPTS['with_description']['user_prompt_template'].format(
            title=req.title,
            description=provided_description
        )
    else:
        system_prompt = MODULE_SURPRISE_ME_PROMPTS['without_description']['system_prompt']
        user_prompt = MODULE_SURPRISE_ME_PROMPTS['without_description']['user_prompt_template'].format(
            title=req.title
        )

    completion = await call_groq_with_timeout(
        client=client,
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        temperature=0.4,
        max_tokens=512,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    generated_description = (completion.choices[0].message.content or "").strip()

    return GenerateResponse(title=(req.title or "").strip(), description=generated_description)


# ============== User Story Endpoints ==============

@router.post("/user-story", response_model=UserStoryResponse)
async def generate_user_story(req: GenerateRequest) -> UserStoryResponse:
    """Generate a complete user story with persona, goal, demographics, and acceptance criteria."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    if Groq is None:
        raise HTTPException(status_code=500, detail="groq package not installed on server")

    client = Groq(api_key=api_key)

    system_prompt = USER_STORY_GENERATION_PROMPTS['system_prompt']
    user_prompt = USER_STORY_GENERATION_PROMPTS['user_prompt_template'].format(
        template_title=req.template.title,
        template_content=req.template.content,
        prompt=req.prompt
    )

    completion = await call_groq_with_timeout(
        client=client,
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        temperature=0.4,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    content = completion.choices[0].message.content or ""

    # Parse JSON response
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start:
            parsed = json.loads(content[start:end])
            
            return UserStoryResponse(
                title=parsed.get("title", req.template.title),
                description=parsed.get("description", ""),
                persona=parsed.get("persona", "[User Persona]"),
                user_goal=parsed.get("user_goal", "[User Goal]"),
                demographics=parsed.get("demographics", "[Target Demographics]"),
                acceptance_criteria=parsed.get("acceptance_criteria", ["[Acceptance Criterion 1]", "[Acceptance Criterion 2]"])
            )
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse user story JSON: {e}. Content preview: {content[:200]}")

    # Fallback response
    return UserStoryResponse(
        title=req.template.title,
        description=f"As a [user], I want [goal] so that [benefit].",
        persona="[Define the user persona]",
        user_goal="[Define the user's goal]",
        demographics="[Define target demographics]",
        acceptance_criteria=["[Acceptance Criterion 1]", "[Acceptance Criterion 2]", "[Acceptance Criterion 3]"]
    )


@router.post("/user-story-surprise-me", response_model=UserStoryResponse)
async def generate_user_story_surprise_me(req: UserStorySurpriseMeRequest) -> UserStoryResponse:
    """Generate or enhance a user story with the 'surprise me' feature."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    if Groq is None:
        raise HTTPException(status_code=500, detail="groq package not installed on server")

    client = Groq(api_key=api_key)

    provided_description = (req.description or "").strip()
    provided_persona = (req.persona or "").strip()
    
    if provided_description or provided_persona:
        system_prompt = USER_STORY_SURPRISE_ME_PROMPTS['with_description']['system_prompt']
        user_prompt = USER_STORY_SURPRISE_ME_PROMPTS['with_description']['user_prompt_template'].format(
            title=req.title,
            description=provided_description or "[Not provided]",
            persona=provided_persona or "[Not provided]"
        )
    else:
        system_prompt = USER_STORY_SURPRISE_ME_PROMPTS['without_description']['system_prompt']
        user_prompt = USER_STORY_SURPRISE_ME_PROMPTS['without_description']['user_prompt_template'].format(
            title=req.title
        )

    completion = await call_groq_with_timeout(
        client=client,
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        temperature=0.4,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    content = completion.choices[0].message.content or ""

    # Parse JSON response
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start:
            parsed = json.loads(content[start:end])
            
            return UserStoryResponse(
                title=parsed.get("title", req.title),
                description=parsed.get("description", ""),
                persona=parsed.get("persona", "[User Persona]"),
                user_goal=parsed.get("user_goal", "[User Goal]"),
                demographics=parsed.get("demographics", "[Target Demographics]"),
                acceptance_criteria=parsed.get("acceptance_criteria", ["[Acceptance Criterion 1]", "[Acceptance Criterion 2]"])
            )
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse user story JSON: {e}. Content preview: {content[:200]}")

    # Fallback response
    return UserStoryResponse(
        title=req.title,
        description=f"As a [user], I want [goal] so that [benefit].",
        persona="[Define the user persona]",
        user_goal="[Define the user's goal]",
        demographics="[Define target demographics]",
        acceptance_criteria=["[Acceptance Criterion 1]", "[Acceptance Criterion 2]", "[Acceptance Criterion 3]"]
    )


# ============== Project Endpoints ==============

def generate_project_id(project_name: str) -> str:
    """Generate project ID from first 5 letters of project name (UPPERCASE)."""
    # Remove non-alphanumeric characters and take first 5 letters
    clean_name = ''.join(c for c in project_name if c.isalnum())
    return clean_name[:5].upper() if clean_name else "PROJE"


@router.post("/project", response_model=ProjectResponse)
async def generate_project(req: GenerateRequest) -> ProjectResponse:
    """Generate a complete project definition with name, ID, and description."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    if Groq is None:
        raise HTTPException(status_code=500, detail="groq package not installed on server")

    client = Groq(api_key=api_key)

    system_prompt = PROJECT_GENERATION_PROMPTS['system_prompt']
    user_prompt = PROJECT_GENERATION_PROMPTS['user_prompt_template'].format(
        template_title=req.template.title,
        template_content=req.template.content,
        prompt=req.prompt
    )

    completion = await call_groq_with_timeout(
        client=client,
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        temperature=0.4,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    content = completion.choices[0].message.content or ""

    # Parse JSON response
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start:
            parsed = json.loads(content[start:end])
            
            project_name = parsed.get("project_name", req.template.title)
            # Use provided project_id or generate from name
            project_id = parsed.get("project_id") or generate_project_id(project_name)
            
            return ProjectResponse(
                project_name=project_name,
                project_id=project_id.upper(),  # Ensure uppercase
                description=parsed.get("description", "")
            )
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse project JSON: {e}. Content preview: {content[:200]}")

    # Fallback response
    fallback_name = req.template.title or "New Project"
    return ProjectResponse(
        project_name=fallback_name,
        project_id=generate_project_id(fallback_name),
        description="## Overview\n[Project description]\n\n## Goals\n- [Goal 1]\n- [Goal 2]\n\n## Scope\n[Define project scope]"
    )


# ============== Feature Endpoints ==============

@router.post("/feature", response_model=FeatureResponse)
async def generate_feature(req: GenerateRequest) -> FeatureResponse:
    """Generate a complete feature specification with requirements, scope, and goals."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    if Groq is None:
        raise HTTPException(status_code=500, detail="groq package not installed on server")

    client = Groq(api_key=api_key)

    system_prompt = FEATURE_GENERATION_PROMPTS['system_prompt']
    user_prompt = FEATURE_GENERATION_PROMPTS['user_prompt_template'].format(
        template_title=req.template.title,
        template_content=req.template.content,
        prompt=req.prompt
    )

    completion = await call_groq_with_timeout(
        client=client,
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        temperature=0.4,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    content = completion.choices[0].message.content or ""

    # Parse JSON response
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start:
            parsed = json.loads(content[start:end])
            
            # Parse functional requirements
            func_reqs = []
            for req_item in parsed.get("functional_requirements", []):
                if isinstance(req_item, dict):
                    func_reqs.append(Requirement(
                        requirement=req_item.get("requirement", "[Requirement]"),
                        type=req_item.get("type", "should_have")
                    ))
            
            # Parse non-functional requirements
            non_func_reqs = []
            for req_item in parsed.get("non_functional_requirements", []):
                if isinstance(req_item, dict):
                    non_func_reqs.append(Requirement(
                        requirement=req_item.get("requirement", "[Requirement]"),
                        type=req_item.get("type", "should_have")
                    ))
            
            return FeatureResponse(
                feature_name=parsed.get("feature_name", req.template.title),
                description=parsed.get("description", "[Feature description]"),
                problem_statement=parsed.get("problem_statement", "[Problem statement]"),
                objective=parsed.get("objective", "[Objective]"),
                success_criteria=parsed.get("success_criteria", ["[Success criterion 1]", "[Success criterion 2]"]),
                goals=parsed.get("goals", ["[Goal 1]", "[Goal 2]"]),
                pain_points=parsed.get("pain_points", ["[Pain point 1]", "[Pain point 2]"]),
                in_scope=parsed.get("in_scope", ["[In scope item 1]", "[In scope item 2]"]),
                out_of_scope=parsed.get("out_of_scope", ["[Out of scope item 1]"]),
                functional_requirements=func_reqs if func_reqs else [
                    Requirement(requirement="[Functional requirement]", type="must_have")
                ],
                non_functional_requirements=non_func_reqs if non_func_reqs else [
                    Requirement(requirement="[Non-functional requirement]", type="must_have")
                ]
            )
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse feature JSON: {e}. Content preview: {content[:200]}")

    # Fallback response
    return FeatureResponse(
        feature_name=req.template.title or "[Feature Name]",
        description="[Provide a comprehensive description of the feature]",
        problem_statement="[Describe the problem this feature solves]",
        objective="[State the primary objective]",
        success_criteria=["[Success criterion 1]", "[Success criterion 2]", "[Success criterion 3]"],
        goals=["[Goal 1]", "[Goal 2]"],
        pain_points=["[Pain point 1]", "[Pain point 2]"],
        in_scope=["[In scope item 1]", "[In scope item 2]", "[In scope item 3]"],
        out_of_scope=["[Out of scope item 1]", "[Out of scope item 2]"],
        functional_requirements=[
            Requirement(requirement="[Must-have functional requirement]", type="must_have"),
            Requirement(requirement="[Should-have functional requirement]", type="should_have"),
            Requirement(requirement="[Nice-to-have functional requirement]", type="nice_to_have")
        ],
        non_functional_requirements=[
            Requirement(requirement="[Performance requirement]", type="must_have"),
            Requirement(requirement="[Security requirement]", type="must_have")
        ]
    )
