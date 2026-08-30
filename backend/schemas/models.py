from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class ActionType(str, Enum):
    NAVIGATE = "navigate"
    FILL = "fill"
    CLICK = "click"
    EXTRACT_PRODUCTS = "extract_products"
    FINISH = "finish"


class Action(BaseModel):
    """The contract a future LLM planner must follow."""

    type: ActionType
    reason: str
    selector: str | None = None
    value: str | None = None


class Product(BaseModel):
    name: str
    price: float = Field(ge=0)
    rating: float = Field(ge=0, le=5)
    url: str
    reason: str | None = None


class StepLog(BaseModel):
    step: int
    action: Action
    observation: str
    screenshot_path: str | None = None


class RunRequest(BaseModel):
    query: str = Field(min_length=1, max_length=80, examples=["无线耳机"])
    max_price: float = Field(gt=0, le=10000, examples=[500])
    min_rating: float = Field(ge=0, le=5, examples=[4.5])
    limit: int = Field(default=3, ge=1, le=5)


class LLMSettings(BaseModel):
    """In-memory configuration for an OpenAI-compatible chat endpoint."""

    base_url: str = Field(default="https://api.openai.com/v1", min_length=8)
    model: str = Field(default="gpt-4.1-mini", min_length=1, max_length=120)
    api_key: str = Field(default="", max_length=500)


class RunResult(BaseModel):
    task: str
    products: list[Product]
    steps: list[StepLog]
    completed: bool
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskRunRequest(BaseModel):
    target_status: str = Field(default="in_progress", pattern="^(todo|in_progress|done)$")
    limit: int = Field(default=2, ge=1, le=3)


class TaskItem(BaseModel):
    id: str
    title: str
    priority: str
    due_date: str
    status: str


class TaskRunResult(BaseModel):
    task: str
    updated_tasks: list[TaskItem]
    steps: list[StepLog]
    completed: bool
    message: str
