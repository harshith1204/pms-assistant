from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from mongo.conversations import conversation_mongo_client, CONVERSATIONS_DB_NAME, TEMPLATES_COLLECTION_NAME

# Pydantic models for API requests/responses
class CreateTemplateRequest(BaseModel):
    user_input: str
    project_id : str
    business_id : str

class GenerateTemplateResponse(BaseModel):
    template: Dict[str, Any]

# Global template generator instance
template_generator = None

def set_template_generator(generator):
    """Set the template generator instance from the main app"""
    global template_generator
    template_generator = generator

router = APIRouter(prefix="/templates", tags=["templates"])

@router.post("/create", response_model=GenerateTemplateResponse)
async def create_template(req: CreateTemplateRequest):
    """
    Generate a structured task template in JSON format based on a user's role, domain, or task description.

    The function analyzes the user's input (e.g., their job role or activity) and infers
    a relevant task structure, including title, content sections, and priority level.
    It is useful for dynamically creating templates that match a user's workflow,
    such as bug reports, research tasks, feature requests, or documentation updates.

    The returned template always includes:
      - id (str): Lowercase, hyphen-separated unique identifier.
      - name (str): Human-readable name of the template.
      - description (str): Short summary of the template's purpose.
      - title (str): Formatted title with an emoji and placeholder.
      - content (str): Markdown-formatted sections (4–6 headings).
      - priority (str): One of "High", "Medium", or "Low" based on task urgency.

    If insufficient context is provided in the input, an error JSON is returned:
        {"error": "Insufficient context. Please describe your role or task type."}

    Example Usage:
        Input:
        {
            "user_input": "I'm a data scientist running model experiments."
        }

        Expected Output:
        {
          "id": "model-experiment",
          "name": "Model Experiment",
          "description": "Template for running and documenting machine learning experiments",
          "title": "🤖 Model Experiment: [Model Name]",
          "content": "## Objective\\n\\n## Hypothesis\\n\\n## Dataset and Features\\n\\n## Model Configuration\\n\\n## Evaluation Metrics\\n\\n## Results and Insights\\n",
          "priority": "High"
        }

    Returns:
        dict: A structured JSON-like dictionary representing the generated task template.
    """
    try:
        if template_generator is None:
            raise HTTPException(status_code=500, detail="Template generator not initialized")

        result = await template_generator.generate_template(
            user_input=req.user_input
        )
        coll = await conversation_mongo_client.get_collection(CONVERSATIONS_DB_NAME, TEMPLATES_COLLECTION_NAME)
        if result:
            await coll.insert_one(
                {
                    "project_id": req.project_id,
                    "business_id": req.business_id,
                    "template": result
                }
            )
        return GenerateTemplateResponse(
            template = result
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
