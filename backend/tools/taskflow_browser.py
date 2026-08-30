from datetime import date

from playwright.async_api import async_playwright

from backend.schemas import TaskItem


class TaskFlowBrowser:
    """Browser tools for a state-changing local task-management environment."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._playwright = None
        self._browser = None
        self._page = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        self._page = await self._browser.new_page(viewport={"width": 1280, "height": 800})
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def open(self) -> str:
        await self._page.goto(self.url, wait_until="networkidle")
        return await self._page.title()

    async def show_high_priority(self) -> None:
        await self._page.locator("#priority-filter").select_option("high")
        await self._page.wait_for_timeout(100)

    async def extract_overdue_todos(self) -> list[TaskItem]:
        today = date.today().isoformat()
        cards = self._page.locator(".task-card")
        tasks: list[TaskItem] = []
        for index in range(await cards.count()):
            card = cards.nth(index)
            item = TaskItem(
                id=await card.get_attribute("data-id"),
                title=await card.locator("[data-field='title']").inner_text(),
                priority=await card.get_attribute("data-priority"),
                due_date=await card.get_attribute("data-due"),
                status=await card.get_attribute("data-status"),
            )
            if item.status == "todo" and item.due_date < today:
                tasks.append(item)
        return sorted(tasks, key=lambda task: task.due_date)

    async def update_status(self, task_id: str, status: str) -> TaskItem:
        card = self._page.locator(f".task-card[data-id='{task_id}']")
        await card.locator("[data-action='status']").select_option(status)
        await self._page.wait_for_timeout(100)
        updated = self._page.locator(f".task-card[data-id='{task_id}']")
        return TaskItem(
            id=task_id,
            title=await updated.locator("[data-field='title']").inner_text(),
            priority=await updated.get_attribute("data-priority"),
            due_date=await updated.get_attribute("data-due"),
            status=await updated.get_attribute("data-status"),
        )
