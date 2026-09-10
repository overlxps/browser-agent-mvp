from dataclasses import dataclass, field

from backend.schemas import Action, ActionType


@dataclass
class RecoveryPolicy:
    max_steps: int = 12
    max_retries_per_action: int = 1
    max_consecutive_failures: int = 2

    consecutive_failures: int = 0
    total_retries: int = 0
    failure_reasons: list[str] = field(default_factory=list)

    def record_success(self) -> None:
        self.consecutive_failures = 0

    def record_failure(self, reason: str) -> None:
        self.consecutive_failures += 1
        self.failure_reasons.append(reason)

    def should_stop(self, step_count: int) -> str | None:
        if step_count >= self.max_steps:
            return f"达到最大步数限制 {self.max_steps}"
        if self.consecutive_failures >= self.max_consecutive_failures:
            return f"连续失败 {self.consecutive_failures} 次"
        return None

    def guard_action(self, action: Action) -> Action | None:
        if action.type == ActionType.ASK_HUMAN:
            return action
        if action.requires_human:
            return Action(type=ActionType.ASK_HUMAN, reason=action.reason, selector=action.selector, value=action.value)
        return action
