from typing import Dict, Any
from pydantic import BaseModel


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

