from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional

from analytics.dashboards.select import select_best_dashboard

router = APIRouter(prefix="/analytics", tags=["analytics"]) 


class SelectRequest(BaseModel):
    prompt: str
    params: Optional[Dict[str, Any]] = None  # reserved for future manual overrides


@router.post("/select")
async def select_dashboard(req: SelectRequest) -> Dict[str, Any]:
    try:
        # For now ignore params override, selection is prompt-driven
        result = select_best_dashboard(req.prompt)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
