import json
from dataclasses import dataclass
from typing import Literal

import httpx

from backend.schemas import Action, ActionType, LLMSettings, RunRequest

Phase = Literal["start", "opened", "searched", "extracted"]
FALLBACK_ACTION: dict[Phase, ActionType] = {
    "start": ActionType.NAVIGATE,
    "opened": ActionType.FILL,
    "searched": ActionType.EXTRACT,
    "extracted": ActionType.FINISH,
}

ALLOWED_ACTIONS: dict[Phase, set[ActionType]] = {
    "start": {ActionType.NAVIGATE},
    "opened": {ActionType.FILL},
    "searched": {ActionType.FILL, ActionType.SELECT, ActionType.EXTRACT},
    "extracted": {ActionType.FILL, ActionType.SELECT, ActionType.FINISH},
}


@dataclass
class PlanDecision:
    action: Action
    source: Literal["llm", "fallback"]


class OpenAICompatiblePlanner:
    """Plans one safe action at a time; invalid choices never reach the browser."""

    def __init__(self, settings: LLMSettings) -> None:
        self.settings = settings

    def _fallback(self, phase: Phase, request: RunRequest) -> PlanDecision:
        action_type = FALLBACK_ACTION[phase]
        if action_type == ActionType.FILL:
            action = Action(
                type=ActionType.FILL,
                reason=f"搜索用户指定的关键词：{request.query}",
                selector="#search-input",
                value=request.query,
            )
        elif action_type == ActionType.EXTRACT:
            action = Action(
                type=ActionType.EXTRACT,
                reason="读取页面商品卡片的结构化字段",
                selector=".product-card",
            )
        elif action_type == ActionType.NAVIGATE:
            action = Action(type=ActionType.NAVIGATE, reason="打开受信任的本地演示商城")
        else:
            action = Action(type=ActionType.FINISH, reason="完成筛选并返回满足条件的推荐")
        return PlanDecision(action, "fallback")

    async def next_action(self, phase: Phase, request: RunRequest, observation: str) -> PlanDecision:
        fallback = self._fallback(phase, request)
        if not self.settings.api_key:
            return fallback
        prompt = {
            "task": request.model_dump(),
            "phase": phase,
            "observation": observation,
            "allowed_actions": [item.value for item in ALLOWED_ACTIONS[phase]],
            "fallback_action": FALLBACK_ACTION[phase].value,
            "rule": "Return only JSON with keys type and reason. Choose one allowed_actions value. If information is insufficient, use fallback_action.",
        }
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    self.settings.base_url.rstrip("/") + "/chat/completions",
                    headers={"Authorization": f"Bearer {self.settings.api_key}"},
                    json={
                        "model": self.settings.model,
                        "temperature": 0,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": "You are a safe browser-task planner."},
                            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                        ],
                    },
                )
                response.raise_for_status()
                raw = response.json()["choices"][0]["message"]["content"]
                decision = json.loads(raw)
                action = Action(
                    type=decision["type"],
                    reason=decision["reason"],
                    selector="#search-input" if decision["type"] == ActionType.FILL else ".product-card" if decision["type"] == ActionType.EXTRACT else None,
                    value=request.query if decision["type"] == ActionType.FILL else None,
                )
                if action.type in ALLOWED_ACTIONS[phase]:
                    return PlanDecision(action, "llm")
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass
        return fallback
