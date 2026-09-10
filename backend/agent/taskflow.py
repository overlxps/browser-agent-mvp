from datetime import date
from pathlib import Path

from backend.agent.memory import AgentMemory
from backend.agent.recovery import RecoveryPolicy
from backend.agent.state_machine import AgentStateMachine
from backend.schemas import Action, ActionType, AgentRunResult, TaskItem, TaskRunRequest
from backend.tools import TaskFlowBrowser

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


class TaskFlowAgent:
    """Task board agent with explicit state-machine execution."""

    def __init__(self, url: str, screenshot_dir: Path | None = None) -> None:
        self.url = url
        self.screenshot_dir = screenshot_dir or Path("runtime/screenshots")

    @staticmethod
    def rank_tasks(tasks: list[TaskItem]) -> list[TaskItem]:
        return sorted(tasks, key=lambda task: (PRIORITY_ORDER.get(task.priority, 9), task.due_date))

    @staticmethod
    def filter_overdue(tasks: list[TaskItem], today: str | None = None) -> list[TaskItem]:
        reference = today or date.today().isoformat()
        overdue = [task for task in tasks if task.status == "todo" and task.due_date < reference]
        return sorted(overdue, key=lambda task: task.due_date)

    async def run_top_priority(self, request: TaskRunRequest) -> AgentRunResult:
        memory = AgentMemory()
        recovery = RecoveryPolicy(max_steps=16)

        async with TaskFlowBrowser(self.url) as browser:
            async def observe() -> str:
                count = await browser._page.locator(".task-card").count()
                return f"当前看板显示 {count} 个任务"

            machine = AgentStateMachine(browser.executor, memory, recovery, observe, self.screenshot_dir)
            await machine.run_action("打开 TaskFlow 看板", Action(type=ActionType.NAVIGATE, reason="打开页面", value=self.url))
            await machine.run_action("等待页面渲染", Action(type=ActionType.WAIT, reason="等待", value="150"))
            all_tasks = await browser.extract_visible_tasks()
            ranked = self.rank_tasks([task for task in all_tasks if task.status == "todo"])
            targets = ranked[: request.limit]
            memory.remember("candidate_count", len(targets))
            memory.remember("targets", [task.model_dump() for task in targets])

            updated: list[TaskItem] = []
            for task in targets:
                verified = await browser.update_status(task.id, request.target_status)
                updated.append(verified)
                await machine.run_action(
                    f"将“{task.title}”标记为 {request.target_status}",
                    Action(
                        type=ActionType.SELECT,
                        reason="更新任务状态并回读验证",
                        selector=f".task-card[data-id='{task.id}'] [data-action='status']",
                        value=request.target_status,
                        expected=request.target_status,
                    ),
                )

            await machine.run_action("完成 TaskFlow 更新", Action(type=ActionType.FINISH, reason="任务完成"))

        return AgentRunResult(
            task="找到优先级最高且截止日期最近的 3 个任务，将它们标记为进行中",
            updated_tasks=updated,
            steps=memory.steps,
            completed=True,
            message=f"已更新 {len(updated)} 个任务。",
            metadata={
                "retry_count": recovery.total_retries,
                "model_calls": machine.model_calls,
                "failure_reasons": recovery.failure_reasons,
                "screenshot_path": str(self.screenshot_dir / f"{machine.run_id}-step-{len(memory.steps)}.png"),
            },
        )

    async def run_overdue_update(self, request: TaskRunRequest) -> AgentRunResult:
        """Find overdue todo tasks and move them to the target status with read-back verification."""
        memory = AgentMemory()
        recovery = RecoveryPolicy(max_steps=16)

        async with TaskFlowBrowser(self.url) as browser:
            async def observe() -> str:
                count = await browser._page.locator(".task-card").count()
                return f"当前看板显示 {count} 个任务"

            machine = AgentStateMachine(browser.executor, memory, recovery, observe, self.screenshot_dir)
            await machine.run_action("打开 TaskFlow 看板", Action(type=ActionType.NAVIGATE, reason="打开页面", value=self.url))
            await machine.run_action("筛选待办任务", Action(type=ActionType.SELECT, reason="只看未开始任务", selector="#status-filter", value="todo"))
            all_todos = await browser.extract_visible_tasks()
            overdue = self.filter_overdue(all_todos)[: request.limit]
            memory.remember("overdue_count", len(overdue))
            memory.remember("overdue_tasks", [task.model_dump() for task in overdue])

            updated: list[TaskItem] = []
            for task in overdue:
                verified = await browser.update_status(task.id, request.target_status)
                updated.append(verified)
                await machine.run_action(
                    f"将逾期任务“{task.title}”（截止 {task.due_date}）标记为 {request.target_status}",
                    Action(
                        type=ActionType.SELECT,
                        reason="更新逾期任务状态并回读验证",
                        selector=f".task-card[data-id='{task.id}'] [data-action='status']",
                        value=request.target_status,
                        expected=request.target_status,
                    ),
                )

            await machine.run_action("完成逾期任务处理", Action(type=ActionType.FINISH, reason="任务完成"))

        return AgentRunResult(
            task="找出所有已逾期的待办任务，将它们标记为进行中",
            updated_tasks=updated,
            steps=memory.steps,
            completed=True,
            message=f"共处理 {len(updated)} 个逾期任务。",
            metadata={
                "retry_count": recovery.total_retries,
                "model_calls": machine.model_calls,
                "failure_reasons": recovery.failure_reasons,
                "screenshot_path": str(self.screenshot_dir / f"{machine.run_id}-step-{len(memory.steps)}.png"),
            },
        )

    async def run(self, request: TaskRunRequest) -> AgentRunResult:
        return await self.run_top_priority(request)

    async def count_done_tasks(self) -> AgentRunResult:
        memory = AgentMemory()
        recovery = RecoveryPolicy(max_steps=8)

        async with TaskFlowBrowser(self.url) as browser:
            async def observe() -> str:
                count = await browser._page.locator(".task-card[data-status='done']").count()
                return f"已完成任务数量：{count}"

            machine = AgentStateMachine(browser.executor, memory, recovery, observe, self.screenshot_dir)
            await machine.run_action("打开 TaskFlow 看板", Action(type=ActionType.NAVIGATE, reason="打开页面", value=self.url))
            count = await browser.filter_status("done")
            tasks = await browser.extract_visible_tasks()
            await machine.run_action(
                "筛选已完成任务",
                Action(type=ActionType.SELECT, reason="状态筛选", selector="#status-filter", value="done"),
            )
            await machine.run_action(
                "验证已完成任务数量",
                Action(type=ActionType.VERIFY, reason="验证数量", selector=".task-card", expected=count),
            )
            await machine.run_action("完成统计", Action(type=ActionType.FINISH, reason="完成"))

        return AgentRunResult(
            task="统计已完成任务数量",
            updated_tasks=tasks,
            steps=memory.steps,
            completed=True,
            message=f"共找到 {count} 个已完成任务。",
            metadata={"done_count": count, "retry_count": recovery.total_retries, "model_calls": machine.model_calls},
        )
