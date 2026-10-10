from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Citation(StrictModel):
    document_id: str
    page: int = Field(ge=1)
    quote: str = Field(min_length=8, max_length=1200)

class Finding(StrictModel):
    title: str = Field(min_length=3, max_length=180)
    kind: Literal['contradiction', 'arithmetic', 'duplicate', 'supported', 'missing_information']
    severity: Literal['info', 'medium', 'high']
    explanation: str = Field(min_length=10, max_length=2500)
    citations: list[Citation] = Field(default_factory=list, max_length=6)
    next_step: str = Field(max_length=800)

class Report(StrictModel):
    summary: str = Field(min_length=10, max_length=2500)
    findings: list[Finding] = Field(default_factory=list, max_length=12)
    unanswered_questions: list[str] = Field(default_factory=list, max_length=10)

class ReviewItem(StrictModel):
    index: int = Field(ge=0)
    verdict: Literal['supported', 'revise', 'unsupported']
    reason: str = Field(min_length=5, max_length=1400)

class Review(StrictModel):
    assessments: list[ReviewItem] = Field(max_length=12)
    summary: str = Field(min_length=5, max_length=1500)

class InvestigationRequest(StrictModel):
    objective: str = Field(min_length=10, max_length=2000)
    mode: Literal['agents', 'baseline', 'offline'] = 'agents'
    allow_external: bool = False

class SearchRequest(StrictModel):
    query: str = Field(min_length=2, max_length=500)

class HumanReview(StrictModel):
    status: Literal['unreviewed', 'accepted', 'needs_followup', 'rejected']
    note: str = Field(default='', max_length=2000)
