import os
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
        # Extract JSON from response
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start:
            parsed = json.loads(content[start:end])
            
            if isinstance(parsed, dict):
                title = parsed.get("title") or title
                raw_blocks = parsed.get("blocks", [])
                
                # Validate and clean blocks
                if isinstance(raw_blocks, list):
                    for i, block in enumerate(raw_blocks):
                        if isinstance(block, dict) and "type" in block and "data" in block:
                            # Ensure block has an ID
                            if "id" not in block:
                                block["id"] = f"blk_{i+1}"
                            blocks.append(block)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON from Groq response: {e}. Content preview: {content[:200]}")

    # Fallback: if no valid blocks, create a simple paragraph block
    if not blocks:
        fallback_text = content.strip() if content.strip() else "Content generation in progress. Please add your content here."
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
