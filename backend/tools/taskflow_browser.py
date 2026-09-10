from playwright.async_api import async_playwright

from backend.agent.executor import BrowserExecutor
from backend.schemas import Action, ActionType, TaskItem


class TaskFlowBrowser:
    """Browser tools for a state-changing local task-management environment."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._playwright = None
        self._browser = None
        self._page = None
        self.executor: BrowserExecutor | None = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        self._page = await self._browser.new_page(viewport={"width": 1280, "height": 800})
        self.executor = BrowserExecutor(self._page)
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def open(self) -> str:
        return await self.executor.execute(Action(type=ActionType.NAVIGATE, reason="打开任务看板", value=self.url))

    async def filter_status(self, status: str) -> int:
        await self.executor.execute(
            Action(type=ActionType.SELECT, reason="按状态筛选任务", selector="#status-filter", value=status)
        )
        return await self._page.locator(".task-card").count()

    async def extract_visible_tasks(self) -> list[TaskItem]:
        cards = self._page.locator(".task-card")
        tasks: list[TaskItem] = []
        for index in range(await cards.count()):
            card = cards.nth(index)
            tasks.append(
                TaskItem(
                    id=await card.get_attribute("data-id"),
                    title=await card.locator("[data-field='title']").inner_text(),
                    priority=await card.get_attribute("data-priority"),
                    due_date=await card.get_attribute("data-due"),
                    status=await card.get_attribute("data-status"),
                )
            )
        return tasks

    async def update_status(self, task_id: str, status: str) -> TaskItem:
        card = self._page.locator(f".task-card[data-id='{task_id}']")
        await self.executor.execute(
            Action(
                type=ActionType.SELECT,
                reason="更新任务状态",
                selector=f".task-card[data-id='{task_id}'] [data-action='status']",
                value=status,
            )
        )
        updated = self._page.locator(f".task-card[data-id='{task_id}']")
        item = TaskItem(
            id=task_id,
            title=await updated.locator("[data-field='title']").inner_text(),
            priority=await updated.get_attribute("data-priority"),
            due_date=await updated.get_attribute("data-due"),
            status=await updated.get_attribute("data-status"),
        )
        await self.executor.execute(
            Action(
                type=ActionType.VERIFY,
                reason="回读任务状态",
                selector=f".task-card[data-id='{task_id}']",
                field="data-status",
                expected=status,
            )
        )
        return item
