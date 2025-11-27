from typing import Dict, Any, Optional, List
from pydantic import BaseModel


class TemplateInput(BaseModel):
    title: str
    content: str


class GenerateRequest(BaseModel):
    prompt: str
    template: TemplateInput


class GenerateResponse(BaseModel):
    title: str
    description: str


class EditorJsBlock(BaseModel):
    id: str
    type: str
    data: Dict[str, Any]


class PageGenerateResponse(BaseModel):
    """Response model for page generation - Editor.js blocks format"""
    title: str
    blocks: List[EditorJsBlock]


class WorkItemSurpriseMeRequest(BaseModel):
    title: str
    description: Optional[str] = None


class CycleSurpriseMeRequest(BaseModel):
    title: str
    description: Optional[str] = None


class ModuleSurpriseMeRequest(BaseModel):
    title: str
    description: Optional[str] = None


class EpicSurpriseMeRequest(BaseModel):
    title: str
    description: Optional[str] = None


# User Story Models
class UserStoryResponse(BaseModel):
    """Response model for user story generation"""
    title: str
    description: str
    persona: str
    user_goal: str
    demographics: str
    acceptance_criteria: List[str]


class UserStorySurpriseMeRequest(BaseModel):
    title: str
    description: Optional[str] = None
    persona: Optional[str] = None


# Project Models
class ProjectResponse(BaseModel):
    """Response model for project generation"""
    project_name: str
    project_id: str  # CAPS of first 5 letters
    description: str

