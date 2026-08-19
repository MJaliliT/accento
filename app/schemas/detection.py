from typing import Literal, Optional

from pydantic import BaseModel, HttpUrl


class AnalysisRequest(BaseModel):
    url: HttpUrl


class AnalysisResponse(BaseModel):
    id: str
    status: Literal["processing", "done", "error"]
    accent: Optional[str] = None
    confidence: Optional[float] = None
    language: Optional[str] = None
    reason: Optional[str] = None
