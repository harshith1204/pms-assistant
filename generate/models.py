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

