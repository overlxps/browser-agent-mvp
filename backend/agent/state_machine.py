from pathlib import Path
from typing import Awaitable, Callable
from uuid import uuid4

from backend.agent.executor import BrowserExecutor, HumanAssistanceRequired
from backend.agent.memory import AgentMemory
from backend.agent.recovery import RecoveryPolicy
from backend.schemas import Action, ActionType, StepLog


ObserveFn = Callable[[], Awaitable[str]]


class AgentStoppedError(RuntimeError):
    """Raised when the safety policy halts the loop before the next action."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AgentStateMachine:
    """Observe → Execute → Verify → Memory loop with safety guards."""

    def __init__(
        self,
        executor: BrowserExecutor,
        memory: AgentMemory,
        recovery: RecoveryPolicy,
        observe: ObserveFn,
        screenshot_dir: Path | None = None,
        run_id: str | None = None,
    ) -> None:
        self.executor = executor
        self.memory = memory
        self.recovery = recovery
        self.observe = observe
        self.screenshot_dir = screenshot_dir
        self.run_id = run_id or uuid4().hex[:8]
        self.model_calls = 0

    async def run_action(
        self,
        goal: str,
        action: Action,
        *,
        planner_source: str = "script",
        verify: bool = True,
    ) -> StepLog:
        stop_reason = self.should_stop()
        if stop_reason:
            recent = "；".join(self.recovery.failure_reasons[-2:]) or "无详细原因"
            raise AgentStoppedError(f"{stop_reason}（最近失败：{recent}）")

        guarded = self.recovery.guard_action(action)
        if guarded and guarded.type == ActionType.ASK_HUMAN:
            return await self._ask_human_step(goal, guarded, planner_source)

        observation_before = await self.observe()
        retry_count = 0
        verified = False
        result = ""
        screenshot_path = None

        try:
            result, retry_count = await self.executor.execute_with_retry(
                action,
                retries=self.recovery.max_retries_per_action,
            )
            self.recovery.total_retries += retry_count
            verified = await self._verify_action(action, observation_before) if verify else False
            self.recovery.record_success()
        except HumanAssistanceRequired as error:
            self.recovery.record_failure(error.message)
            return await self._ask_human_step(goal, Action(type=ActionType.ASK_HUMAN, reason=error.message), planner_source)
        except Exception as error:
            self.recovery.record_failure(str(error))
            result = f"动作失败：{error}"
            verified = False

        if self.screenshot_dir is not None:
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)
            screenshot_path = str(self.screenshot_dir / f"{self.run_id}-step-{len(self.memory.steps) + 1}.png")
            await self.executor.page.screenshot(path=screenshot_path, full_page=True)

        step = StepLog(
            step=len(self.memory.steps) + 1,
            goal=goal,
            action=action,
            target=action.selector,
            observation_before=observation_before,
            result=result,
            verified=verified,
            screenshot_path=screenshot_path,
            planner_source=planner_source,  # type: ignore[arg-type]
            retry_count=retry_count,
            model_calls=self.model_calls,
        )
        self.memory.record_step(step)
        return step

    async def _verify_action(self, action: Action, observation_before: str) -> bool:
        """Read back page state after an action instead of assuming success."""
        page = self.executor.page
        try:
            if action.type == ActionType.NAVIGATE:
                return bool(await page.title())
            if action.type in {ActionType.FILL, ActionType.SELECT} and action.selector:
                actual = await page.locator(action.selector).input_value(timeout=2000)
                return str(actual) == str(action.value or "")
            if action.type == ActionType.CLICK:
                observation_after = await self.observe()
                if observation_after != observation_before:
                    return True
                if action.selector:
                    try:
                        return await page.locator(action.selector).first.is_visible()
                    except Exception:
                        return False
                return True
            if action.type == ActionType.VERIFY:
                return True
            if action.type == ActionType.EXTRACT:
                return True
            return True
        except Exception:
            return False

    async def _ask_human_step(self, goal: str, action: Action, planner_source: str) -> StepLog:
        observation_before = await self.observe()
        step = StepLog(
            step=len(self.memory.steps) + 1,
            goal=goal,
            action=action,
            target=action.selector,
            observation_before=observation_before,
            result="已暂停并请求人工帮助。",
            verified=False,
            planner_source=planner_source,  # type: ignore[arg-type]
            retry_count=0,
            model_calls=self.model_calls,
        )
        self.memory.record_step(step)
        return step

    def should_stop(self) -> str | None:
        return self.recovery.should_stop(len(self.memory.steps))
