from dataclasses import dataclass, field

from backend.schemas import StepLog


@dataclass
class AgentMemory:
    """Stores prior observations and extracted facts for the current run."""

    facts: dict[str, object] = field(default_factory=dict)
    steps: list[StepLog] = field(default_factory=list)

    def record_step(self, step: StepLog) -> None:
        self.steps.append(step)

    def remember(self, key: str, value: object) -> None:
        self.facts[key] = value

    def recall(self, key: str, default: object | None = None) -> object | None:
        return self.facts.get(key, default)

    def summarize(self) -> str:
        if not self.facts:
            return "尚无结构化记忆。"
        return "；".join(f"{key}={value}" for key, value in self.facts.items())
