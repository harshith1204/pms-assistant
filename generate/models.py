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


# Feature Models
class Requirement(BaseModel):
    """Requirement with priority type"""
    requirement: str
    type: str  # "must_have", "should_have", "nice_to_have"


class FeatureResponse(BaseModel):
    """Response model for feature generation"""
    feature_name: str
    description: str
    problem_statement: str
    objective: str
    success_criteria: List[str]
    goals: List[str]
    pain_points: List[str]
    in_scope: List[str]
    out_of_scope: List[str]
    functional_requirements: List[Requirement]
    non_functional_requirements: List[Requirement]


class FeatureSurpriseMeRequest(BaseModel):
    """Request model for feature surprise-me generation"""
    feature_name: str
    description: Optional[str] = None
    problem_statement: Optional[str] = None


class ProjectSurpriseMeRequest(BaseModel):
    """Request model for project surprise-me generation"""
    project_name: str
    description: Optional[str] = None


class PageSurpriseMeRequest(BaseModel):
    """Request model for page surprise-me generation"""
    title: str
    content: Optional[str] = None

