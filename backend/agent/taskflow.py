from backend.schemas import Action, ActionType, StepLog, TaskRunRequest, TaskRunResult
from backend.tools import TaskFlowBrowser


class TaskFlowAgent:
    """A task-operating Agent with explicit before/after state verification."""

    def __init__(self, url: str) -> None:
        self.url = url

    async def run(self, request: TaskRunRequest) -> TaskRunResult:
        steps: list[StepLog] = []

        def log(action: Action, observation: str) -> None:
            steps.append(StepLog(step=len(steps) + 1, action=action, observation=observation))

        async with TaskFlowBrowser(self.url) as browser:
            title = await browser.open()
            log(Action(type=ActionType.NAVIGATE, reason="打开本地任务管理环境"), f"已打开：{title}")
            await browser.show_high_priority()
            log(Action(type=ActionType.CLICK, reason="筛选高优先级任务", selector="#priority-filter"), "页面仅显示高优先级任务。")
            candidates = await browser.extract_overdue_todos()
            log(Action(type=ActionType.EXTRACT_PRODUCTS, reason="识别待办且已逾期的任务"), f"找到 {len(candidates)} 个高优先级逾期待办任务。")
            updated = []
            for task in candidates[: request.limit]:
                verified = await browser.update_status(task.id, request.target_status)
                if verified.status != request.target_status:
                    raise RuntimeError(f"任务 {task.id} 状态验证失败")
                updated.append(verified)
                log(Action(type=ActionType.CLICK, reason="更新任务状态并验证", selector=f"[data-id='{task.id}']"), f"已将“{task.title}”更新为 {request.target_status}。")
        log(Action(type=ActionType.FINISH, reason="目标任务已更新并完成验证"), f"共更新 {len(updated)} 个任务。")
        return TaskRunResult(
            task="将高优先级且已逾期的待办任务标记为进行中",
            updated_tasks=updated,
            steps=steps,
            completed=True,
            message="任务完成：每项状态均已在页面中回读验证。",
        )
