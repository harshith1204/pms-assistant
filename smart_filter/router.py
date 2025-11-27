from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# Smart Filter API Models
class SmartFilterRequest(BaseModel):
    query: str
    project_id: str
    limit: Optional[int] = 50


class WorkItemState(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None


class WorkItemStateMaster(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None


class WorkItemAssignee(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None


class WorkItemLabel(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    color: Optional[str] = None


class WorkItemAttachment(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None


class WorkItemModules(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None


class WorkItemCycle(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None


class WorkItemBusiness(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None


class WorkItemLead(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None


class WorkItemProject(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None


class WorkItemCreatedBy(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None


class WorkItemUpdatedBy(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None


class WorkItemParent(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None


class WorkItemUserStory(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None


class WorkItemFeature(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None


class WorkItemEpic(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None


class WorkItemEstimate(BaseModel):
    hr: Optional[str] = None
    min: Optional[str] = None


class WorkItem(BaseModel):
    # Core required fields
    title: str
    stateMaster: WorkItemStateMaster
    state: WorkItemState
    createdTimeStamp: str
    updatedTimeStamp: str

    # Optional fields that exist in data
    description: Optional[str] = None
    business: Optional[WorkItemBusiness] = None
    priority: Optional[str] = None
    assignee: List[WorkItemAssignee] = Field(default_factory=list)
    label: List[WorkItemLabel] = Field(default_factory=list)
    cycle: Optional[WorkItemCycle] = None
    modules: Optional[WorkItemModules] = None
    parent: Optional[WorkItemParent] = None
    project: Optional[WorkItemProject] = None
    displayBugNo: Optional[str] = None
    status: Optional[str] = None
    createdBy: Optional[WorkItemCreatedBy] = None
    updatedBy: List[WorkItemUpdatedBy] = Field(default_factory=list)
    userStory: Optional[WorkItemUserStory] = None
    feature: Optional[WorkItemFeature] = None
    epic: Optional[WorkItemEpic] = None

    # Fields for future compatibility (not currently in data)
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    releaseDate: Optional[str] = None
    lead: Optional[WorkItemLead] = None
    attachmentUrl: List[WorkItemAttachment] = Field(default_factory=list)
    workLogs: Optional[List[Any]] = None
    estimateSystem: Optional[str] = None
    estimate: Optional[WorkItemEstimate] = None
    id: Optional[str] = None
    view: Optional[str] = None
    link: Optional[str] = None
    subWorkItems: Optional[List[Any]] = None
    timeline: Optional[List[Any]] = None


class SmartFilterResponse(BaseModel):
    data: List[WorkItem]

# Global smart filter agent instance
smart_filter_agent = None

def set_smart_filter_agent(agent):
    """Set the smart filter agent instance from the main app"""
    global smart_filter_agent
    smart_filter_agent = agent

router = APIRouter(prefix="/smart-filter", tags=["smart-filter"])

@router.post("/work-items", response_model=SmartFilterResponse)
async def smart_filter_work_items(req: SmartFilterRequest):
    """Smart filter work items using RAG + MongoDB queries based on natural language.

    This endpoint combines retrieval-augmented generation (RAG) with MongoDB aggregation
    pipelines to intelligently filter work items based on natural language queries.

    The process:
    1. Uses RAG to find relevant documents and extract work item references
    2. Parses the natural language query to extract filtering criteria
    3. Builds and executes optimized MongoDB aggregation pipeline
    4. Returns work items in the exact API response structure

    Example queries:
    - "high priority bugs assigned to John"
    - "tasks due this week in the authentication module"
    - "completed features in sprint 3"
    - "work items with 'login' in the title"
    """
    try:
        if smart_filter_agent is None:
            raise HTTPException(status_code=500, detail="Smart filter agent not initialized")

        result = await smart_filter_agent.smart_filter_work_items(
            query=req.query,
            project_id=req.project_id,
            limit=req.limit or 50
        )

        return SmartFilterResponse(
            data=result.work_items
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
