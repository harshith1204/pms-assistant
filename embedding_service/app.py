from __future__ import annotations

from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from encoder import get_encoder


class EmbedRequest(BaseModel):
    inputs: List[str] = Field(default_factory=list)
    normalize: Optional[bool] = None


class EmbedResponse(BaseModel):
    embeddings: List[List[float]]


app = FastAPI(title="Embedding Service", version="1.0.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/dimension")
async def dimension() -> dict[str, int]:
    encoder = get_encoder()
    return {"dimension": encoder.dimension}


@app.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest) -> EmbedResponse:
    encoder = get_encoder()
    if not request.inputs:
        return EmbedResponse(embeddings=[])

    vectors = encoder.encode(request.inputs, normalize=request.normalize)
    if any(not isinstance(vec, list) for vec in vectors):
        raise HTTPException(status_code=500, detail="Invalid embedding output format")
    return EmbedResponse(embeddings=vectors)


def create_app() -> FastAPI:
    return app
