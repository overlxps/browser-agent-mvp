from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    SELECT = "select"
    SCROLL = "scroll"
    EXTRACT = "extract"
    WAIT = "wait"
    VERIFY = "verify"
    FINISH = "finish"
    ASK_HUMAN = "ask_human"


ALLOWED_ACTIONS = {
    ActionType.NAVIGATE,
    ActionType.CLICK,
    ActionType.FILL,
    ActionType.SELECT,
    ActionType.SCROLL,
    ActionType.EXTRACT,
    ActionType.WAIT,
    ActionType.VERIFY,
    ActionType.FINISH,
    ActionType.ASK_HUMAN,
}

HIGH_RISK_ACTIONS = {ActionType.ASK_HUMAN}


class Action(BaseModel):
    """The contract a planner or executor must follow."""

    type: ActionType
    reason: str
    selector: str | None = None
    value: str | None = None
    field: str | None = None
    expected: str | float | int | bool | None = None
    requires_human: bool = False


class Product(BaseModel):
    name: str
    price: float = Field(ge=0)
    rating: float = Field(ge=0, le=5)
    url: str
    reason: str | None = None
    stock: int | None = None


class Hotel(BaseModel):
    id: str
    name: str
    price: float = Field(ge=0)
    rating: float = Field(ge=0, le=5)
    city: str
    weekend_available: bool = True
    reason: str | None = None


class StepLog(BaseModel):
    step: int
    goal: str
    action: Action
    target: str | None = None
    observation_before: str
    result: str
    verified: bool
    screenshot_path: str | None = None
    planner_source: Literal["llm", "fallback", "script"] = "fallback"
    retry_count: int = 0
    model_calls: int = 0

    @property
    def observation(self) -> str:
        return self.result


class RunRequest(BaseModel):
    query: str = Field(min_length=1, max_length=80, examples=["无线耳机"])
    max_price: float = Field(gt=0, le=10000, examples=[500])
    min_rating: float = Field(ge=0, le=5, examples=[4.5])
    limit: int = Field(default=3, ge=1, le=5)


class TravelRunRequest(BaseModel):
    month: str = Field(default="2026-09", pattern=r"^\d{4}-\d{2}$")
    max_price: float = Field(default=800, gt=0, le=10000)
    min_rating: float = Field(default=4.5, ge=0, le=5)
    limit: int = Field(default=2, ge=1, le=5)
    weekend_only: bool = True


class LLMSettings(BaseModel):
    base_url: str = Field(default="https://api.openai.com/v1", min_length=8)
    model: str = Field(default="gpt-4.1-mini", min_length=1, max_length=120)
    api_key: str = Field(default="", max_length=500)


class AgentRunResult(BaseModel):
    task: str
    steps: list[StepLog]
    completed: bool
    message: str
    products: list[Product] = Field(default_factory=list)
    hotels: list[Hotel] = Field(default_factory=list)
    recommendation: Hotel | None = None
    updated_tasks: list["TaskItem"] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


RunResult = AgentRunResult


class TaskRunRequest(BaseModel):
    target_status: str = Field(default="in_progress", pattern="^(todo|in_progress|done)$")
    limit: int = Field(default=3, ge=1, le=5)


class TaskItem(BaseModel):
    id: str
    title: str
    priority: str
    due_date: str
    status: str


TaskRunResult = AgentRunResult


class EvalCheckResult(BaseModel):
    name: str
    passed: bool
    detail: str


class EvalTaskResult(BaseModel):
    task_id: str
    site: str
    description: str
    instruction: str = ""
    passed: bool
    duration_ms: int
    step_count: int
    retry_count: int = 0
    model_calls: int = 0
    failure_reason: str | None = None
    failure_category: str | None = None
    screenshot_path: str | None = None
    checks: list[EvalCheckResult]
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalRunReport(BaseModel):
    report_id: str
    created_at: str
    passed: bool
    total: int
    passed_count: int
    failed_count: int
    duration_ms: int
    success_rate: float = 0.0
    average_duration_ms: float = 0.0
    average_steps: float = 0.0
    average_retries: float = 0.0
    failure_reasons: list[str] = Field(default_factory=list)
    failure_categories: dict[str, int] = Field(default_factory=dict)
    results: list[EvalTaskResult]
