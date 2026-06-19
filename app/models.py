from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TraceStatus(str, Enum):
    success = "success"
    error = "error"
    timeout = "timeout"


class TraceCreate(BaseModel):
    service: str = Field(min_length=2, max_length=64)
    operation: str = Field(min_length=2, max_length=64)
    model: str = Field(min_length=2, max_length=64)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    status: TraceStatus = TraceStatus.success
    input_preview: str = Field(default="", max_length=500)
    output_preview: str = Field(default="", max_length=500)
    metadata: dict[str, str] = Field(default_factory=dict)


class TraceRecord(TraceCreate):
    id: str
    created_at: datetime


class GoldenItem(BaseModel):
    id: str
    question: str
    expected_answer: str
    reference_context: str
    tags: list[str] = Field(default_factory=list)


class DatasetCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=500)
    items: list[GoldenItem] = Field(min_length=1)


class DatasetSummary(BaseModel):
    id: str
    name: str
    description: str
    item_count: int
    created_at: datetime


class EvaluationRequest(BaseModel):
    dataset_id: str
    run_name: str = Field(min_length=2, max_length=80)
    use_llm_judge: bool | None = None


class QuestionScore(BaseModel):
    item_id: str
    question: str
    generated_answer: str
    faithfulness: float
    answer_relevance: float
    context_precision: float
    latency_ms: int
    passed: bool


class EvaluationRun(BaseModel):
    id: str
    dataset_id: str
    run_name: str
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    summary: dict[str, float] = Field(default_factory=dict)
    results: list[QuestionScore] = Field(default_factory=list)


class MetricsSummary(BaseModel):
    total: int
    passed: int
    failed: int
    avg_faithfulness: float
    avg_answer_relevance: float
    avg_context_precision: float
    avg_latency_ms: float
    pass_rate: float
