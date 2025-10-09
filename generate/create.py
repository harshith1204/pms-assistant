import os
import json
import asyncio
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Environment variables loaded from .env file")
except ImportError:
    print("python-dotenv not installed, will use system env vars")
    pass

try:
    from groq import Groq
except Exception:
    Groq = None  # type: ignore


class TemplateInput(BaseModel):
    title: str
    content: str


class ContextEnvelope(BaseModel):
    tenantId: str
    page: Dict[str, Any]
    subject: Dict[str, Any]
    timeScope: Dict[str, Any]
    retrieval: Dict[str, Any]
    privacy: Dict[str, Any]


class GenerateRequest(BaseModel):
    prompt: str
    template: TemplateInput


class GenerateResponse(BaseModel):
    title: str
    description: str


class PageGenerateRequest(BaseModel):
    context: ContextEnvelope
    template: TemplateInput
    prompt: str
    pageId: str
    projectId: str
    tenantId: str


app = FastAPI(title="AI Template Service", version="0.1.0")

# CORS - allow local dev and any configured origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # allow all origins
    allow_credentials=False, # must be False when using "*"
    allow_methods=["*"],     # allow all HTTP methods
    allow_headers=["*"],     # allow all headers
)

# Page Type Prompt Dictionary - Business-focused prompts for each template type
PAGE_TYPE_PROMPTS = {
    'PROJECT': """
**Project Management Context:**
- Focus on project lifecycle, deliverables, and strategic objectives
- Include KPIs, milestones, risk assessment, and team performance metrics
- Structure for executive decision-making and stakeholder communication
- Adapt content based on specific project template: Status Reports, Risk Registers, or OKR Summaries

**Key Elements to Include:**
- Executive Summary with project status and key achievements
- KPI Dashboard with measurable metrics and progress indicators
- Milestone Timeline with completion status and upcoming deadlines
- Risk Register with impact assessment and mitigation strategies (for Risk Register template)
- OKR Framework with objectives, key results, and progress tracking (for OKR Summary template)
- Team Performance metrics and resource allocation insights
- Budget Tracking summary and financial performance indicators
- Critical Path Analysis and dependency mapping

**Business Standards:**
- Use humanized, conversational language that feels natural and approachable while maintaining professionalism
- Present data-driven insights with actionable recommendations in an engaging, readable format
- Maintain professional yet warm tone suitable for executive reporting that builds trust and clarity
- Include success criteria and measurable outcomes for each section with clear, relatable explanations
- Adapt tone and focus based on template type: more analytical for Risk Registers, more strategic for OKR Summaries
""",

    'TASK': """
**Task Management Context:**
- Focus on specific work items, deliverables, and action-oriented outcomes
- Provide detailed breakdown of requirements and execution steps
- Structure for clear task ownership and accountability

**Key Elements to Include:**
- Task Overview with clear objectives and success criteria
- Detailed Requirements breakdown with acceptance criteria
- Step-by-Step Execution Plan with dependencies and prerequisites
- Resource Requirements including skills, tools, and time estimates
- Deliverables Specification with quality standards and formats
- Risk Assessment for potential blockers and mitigation strategies
- Success Metrics and completion validation criteria

**Business Standards:**
- Use humanized, conversational language that's easy to understand and follow, like explaining to a colleague
- Include measurable outcomes and quality checkpoints with practical, relatable examples
- Structure for easy progress tracking and status updates that feel collaborative and supportive
- Maintain professional yet approachable tone appropriate for technical teams that encourages clarity
""",

    'MEETING': """
**Meeting Management Context:**
- Focus on structured discussion, decision-making, and action tracking
- Capture agenda items, outcomes, and follow-up requirements
- Structure for effective meeting facilitation and documentation

**Key Elements to Include:**
- Meeting Overview with purpose, objectives, and expected outcomes
- Participant List with roles and responsibilities
- Structured Agenda with time allocations and discussion topics
- Key Discussion Points with decisions and rationale
- Action Items with clear ownership, deadlines, and deliverables
- Decision Log with outcomes and supporting information
- Follow-up Requirements and next steps

**Business Standards:**
- Use humanized, conversational language that captures the natural flow of discussion and decisions
- Include specific decisions and assigned responsibilities with context that makes sense to participants
- Structure for easy reference and follow-up tracking that feels like a natural meeting summary
- Maintain professional yet conversational tone suitable for organizational records that people actually read
""",

    'DOCUMENTATION': """
**Documentation Context:**
- Focus on knowledge transfer, process documentation, and reference materials
- Provide clear explanations, procedures, and guidelines
- Structure for easy comprehension and future reference
- Adapt content for different documentation types: General Documentation or Release Notes

**Key Elements to Include:**
- Document Purpose and scope definition
- Target Audience identification and knowledge prerequisites
- Step-by-Step Instructions or procedures with clear workflows
- Key Concepts and terminology definitions
- Best Practices and guidelines for implementation
- Release Highlights, changes, and version information (for Release Notes template)
- Troubleshooting section with common issues and solutions
- Reference Materials and additional resources

**Business Standards:**
- Use humanized, conversational language that explains concepts like you're teaching a friend or colleague
- Include visual aids, diagrams, and screenshots where helpful with friendly, practical guidance
- Structure for logical flow and easy navigation that feels intuitive and user-friendly
- Maintain professional yet approachable tone appropriate for technical documentation that invites learning
- For Release Notes: Use engaging, highlight-focused language that celebrates achievements and improvements
""",

    'KB': """
**Knowledge Base Context:**
- Focus on quick access information, frequently asked questions, and problem-solving
- Provide concise, searchable content for immediate reference
- Structure for rapid information retrieval and self-service

**Key Elements to Include:**
- Question-Answer Format for common inquiries
- Quick Reference Guides for standard procedures
- Troubleshooting Steps for common technical issues
- Best Practices and tips for efficient workflows
- Glossary of Terms for quick definitions
- Related Articles and cross-references

**Business Standards:**
- Use humanized, conversational language that's friendly and reassuring, like helping a colleague in need
- Include search-friendly keywords and clear categorization that makes finding information effortless
- Structure for easy browsing and information discovery that feels like natural conversation
- Maintain helpful, supportive tone for user assistance that builds confidence and reduces frustration
"""
}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate-work-item", response_model=GenerateResponse)
def generate_work_item(req: GenerateRequest):
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
    import json
    title = req.template.title
    description = req.template.content
    parsed = None
    try:
        # Try to find the first JSON object in content
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
        # Fallback: treat entire content as description and synthesize a title
        description = content.strip() or description
        # Simple heuristic: first line up to 120 chars
        first_line = description.splitlines()[0] if description else req.prompt
        title = first_line[:120]

    return GenerateResponse(title=title.strip(), description=description.strip())


# Page content generation (non-streaming)
@app.options("/stream-page-content")
async def options_page_content():
    """Handle CORS preflight requests"""
    return {"message": "OK"}

@app.get("/stream-page-content")
async def generate_page_content(request: Request):
    """Generate complete page content in one response"""
    try:
        # Get data from query parameters
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

    # Build system prompt using context envelope
    context = req.context
    page_type = context.page.get('type', 'DOCUMENTATION')

    # Get the appropriate prompt dictionary for the page type
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
        # Use regular (non-streaming) completion
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

        # Parse the JSON response to extract blocks
        try:
            parsed_response = json.loads(content)
            if "blocks" in parsed_response and isinstance(parsed_response["blocks"], list):
                return parsed_response
            else:
                # Fallback: create a simple paragraph block if parsing fails
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
            # Fallback: create a simple paragraph block if JSON parsing fails
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 7000)), reload=True)

