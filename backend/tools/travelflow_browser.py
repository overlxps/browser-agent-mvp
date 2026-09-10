from pathlib import Path

from playwright.async_api import async_playwright

from backend.agent.executor import BrowserExecutor
from backend.schemas import Action, ActionType, Hotel


class TravelFlowBrowser:
    """Browser tools for hotel search, filtering, and comparison."""

    def __init__(self, url: str, screenshot_dir: Path) -> None:
        self.url = url
        self.screenshot_dir = screenshot_dir
        self._playwright = None
        self._browser = None
        self._page = None
        self.executor: BrowserExecutor | None = None

    async def __aenter__(self):
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
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
        return await self.executor.execute(Action(type=ActionType.NAVIGATE, reason="打开 TravelFlow", value=self.url))

    PRICE_OPTIONS = ["600", "800", "1000"]
    RATING_OPTIONS = ["4.5", "4.7"]

    @staticmethod
    def _threshold_option(options: list[str], required: float, is_upper_bound: bool) -> str:
        """Pick a discrete filter option whose result set is a superset of the requirement.

        The agent re-filters exact bounds in Python afterwards. Returns "" (no filter)
        when no option can express the bound without over-filtering.
        """
        numeric = sorted(float(option) for option in options)
        if is_upper_bound:
            candidates = [value for value in numeric if value >= required]
            value = min(candidates) if candidates else None
        else:
            candidates = [value for value in numeric if value <= required]
            value = max(candidates) if candidates else None
        if value is None:
            return ""
        return str(int(value)) if value == int(value) else str(value)

    @classmethod
    def price_option(cls, max_price: float) -> str:
        return cls._threshold_option(cls.PRICE_OPTIONS, max_price, is_upper_bound=True)

    @classmethod
    def rating_option(cls, min_rating: float) -> str:
        return cls._threshold_option(cls.RATING_OPTIONS, min_rating, is_upper_bound=False)

    async def apply_filters(self, month: str, max_price: float, min_rating: float, weekend_only: bool = True) -> int:
        await self.executor.execute(Action(type=ActionType.SELECT, reason="选择月份", selector="#month-filter", value=month))
        await self.executor.execute(
            Action(type=ActionType.SELECT, reason="选择周末出行", selector="#weekend-filter", value="weekend" if weekend_only else "all")
        )
        price_value = self.price_option(max_price)
        rating_value = self.rating_option(min_rating)
        if price_value:
            await self.executor.execute(Action(type=ActionType.SELECT, reason="选择价格上限", selector="#price-filter", value=price_value))
        if rating_value:
            await self.executor.execute(Action(type=ActionType.SELECT, reason="选择最低评分", selector="#rating-filter", value=rating_value))
        await self.executor.execute(Action(type=ActionType.CLICK, reason="提交搜索", selector="#search-button"))
        await self._page.wait_for_timeout(150)
        return await self._page.locator(".hotel-card").count()

    async def extract_hotels(self) -> list[Hotel]:
        cards = self._page.locator(".hotel-card")
        hotels: list[Hotel] = []
        for index in range(await cards.count()):
            card = cards.nth(index)
            hotels.append(
                Hotel(
                    id=await card.get_attribute("data-id"),
                    name=await card.locator("[data-field='name']").inner_text(),
                    price=float(await card.get_attribute("data-price")),
                    rating=float(await card.get_attribute("data-rating")),
                    city=(await card.locator(".tag").inner_text()).split("·")[0].strip(),
                    weekend_available=(await card.get_attribute("data-weekend")) == "true",
                )
            )
        return hotels

    async def read_recommendation(self) -> str:
        await self._page.wait_for_selector("#comparison:not([hidden]) [data-field='recommendation']", timeout=5000)
        return await self._page.locator("[data-field='recommendation']").inner_text()

    async def screenshot(self, name: str) -> str:
        path = self.screenshot_dir / f"{name}.png"
        await self._page.screenshot(path=str(path), full_page=True)
        return str(path)
