from pathlib import Path
from urllib.parse import quote

from playwright.async_api import async_playwright

from backend.agent.executor import BrowserExecutor
from backend.schemas import Action, ActionType, Product


class DemoStoreBrowser:
    """Small, deterministic Playwright tool layer for the local demo store."""

    def __init__(self, store_url: str, screenshot_dir: Path) -> None:
        self.store_url = store_url.rstrip("/")
        self.screenshot_dir = screenshot_dir
        self._playwright = None
        self._browser = None
        self._page = None
        self.executor: BrowserExecutor | None = None

    async def __aenter__(self):
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._playwright = await async_playwright().start()
        except NotImplementedError as error:
            raise RuntimeError("Playwright runtime could not start") from error
        try:
            self._browser = await self._playwright.chromium.launch(headless=True)
        except NotImplementedError as error:
            raise RuntimeError("Playwright Chromium could not launch") from error
        try:
            self._page = await self._browser.new_page(viewport={"width": 1280, "height": 800})
            self.executor = BrowserExecutor(self._page)
        except NotImplementedError as error:
            raise RuntimeError("Playwright could not create a browser page") from error
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def open_store(self) -> str:
        return await self.executor.execute(Action(type=ActionType.NAVIGATE, reason="打开商城", value=self.store_url))

    async def search(self, query: str) -> int:
        await self.executor.execute(Action(type=ActionType.FILL, reason="填写搜索词", selector="#search-input", value=query))
        await self.executor.execute(Action(type=ActionType.CLICK, reason="提交搜索", selector="#search-button"))
        await self._page.wait_for_selector(".product-card, .empty")
        return await self._page.locator(".product-card").count()

    PRICE_OPTIONS = ["300", "500", "800"]
    RATING_OPTIONS = ["4.5", "4.7"]

    @staticmethod
    def _threshold_option(options: list[str], required: float, is_upper_bound: bool) -> str:
        """Pick a discrete filter option whose result set is a superset of the requirement.

        For a price cap the page option must be >= required (smallest such); for a rating
        floor it must be <= required (largest such). The agent re-filters exact bounds in
        Python afterwards. Returns "" (no filter) when no option can express the bound.
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

    async def apply_filters(self, max_price: float, min_rating: float, category: str | None = None) -> int:
        """Apply native ShopFlow filters and verify the rendered result count."""
        if category:
            await self.executor.execute(
                Action(type=ActionType.SELECT, reason="选择分类", selector="#category-filter", value=category)
            )
        price_value = self.price_option(max_price)
        rating_value = self.rating_option(min_rating)
        if price_value:
            await self.executor.execute(
                Action(type=ActionType.SELECT, reason="选择价格上限", selector="#price-filter", value=price_value)
            )
        if rating_value:
            await self.executor.execute(
                Action(type=ActionType.SELECT, reason="选择最低评分", selector="#rating-filter", value=rating_value)
            )
        await self._page.wait_for_timeout(100)
        return await self._page.locator(".product-card").count()

    async def apply_sort(self, sort_value: str) -> None:
        await self.executor.execute(
            Action(type=ActionType.SELECT, reason="选择排序方式", selector="#sort-filter", value=sort_value)
        )
        await self._page.wait_for_timeout(100)

    async def extract_products(self) -> list[Product]:
        cards = self._page.locator(".product-card")
        products: list[Product] = []
        for index in range(await cards.count()):
            card = cards.nth(index)
            product_id = await card.get_attribute("data-id")
            if product_id is None:
                raise ValueError("商品卡片缺少 data-id")
            products.append(
                Product(
                    name=await card.locator("[data-field='name']").inner_text(),
                    price=float(await card.get_attribute("data-price")),
                    rating=float(await card.get_attribute("data-rating")),
                    url=f"{self.store_url}/product/{quote(product_id)}",
                )
            )
        return products

    async def extract_all_pages(self) -> list[Product]:
        """Read every result page instead of assuming all candidates fit in one viewport."""
        collected: list[Product] = []
        seen_ids: set[str] = set()
        while True:
            for product in await self.extract_products():
                if product.url not in seen_ids:
                    collected.append(product)
                    seen_ids.add(product.url)
            next_button = self._page.locator("#next-page")
            if await next_button.is_disabled():
                return collected
            await self.executor.execute(Action(type=ActionType.CLICK, reason="翻到下一页", selector="#next-page"))
            await self._page.wait_for_timeout(100)

    async def open_product_detail(self, product_id: str) -> dict[str, str]:
        await self.executor.execute(
            Action(type=ActionType.CLICK, reason="打开商品详情", selector=f"[data-product-id='{product_id}']")
        )
        return await self.read_product_detail()

    async def read_product_detail(self) -> dict[str, str]:
        await self._page.wait_for_selector("#detail-content [data-field='stock']")
        detail = self._page.locator("#detail-content")
        return {
            "name": await detail.locator("[data-field='name']").inner_text(),
            "price": await detail.locator("[data-field='price']").inner_text(),
            "rating": await detail.locator("[data-field='rating']").inner_text(),
            "stock": await detail.locator("[data-field='stock']").inner_text(),
        }

    async def screenshot(self, name: str) -> str:
        path = self.screenshot_dir / f"{name}.png"
        await self._page.screenshot(path=str(path), full_page=True)
        return str(path)
