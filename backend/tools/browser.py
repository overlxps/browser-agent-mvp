from pathlib import Path
from urllib.parse import quote

from playwright.async_api import async_playwright

from backend.schemas import Product


class DemoStoreBrowser:
    """Small, deterministic Playwright tool layer for the local demo store."""

    def __init__(self, store_url: str, screenshot_dir: Path) -> None:
        self.store_url = store_url.rstrip("/")
        self.screenshot_dir = screenshot_dir
        self._playwright = None
        self._browser = None
        self._page = None

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
        except NotImplementedError as error:
            raise RuntimeError("Playwright could not create a browser page") from error
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def open_store(self) -> str:
        try:
            await self._page.goto(self.store_url, wait_until="networkidle")
        except NotImplementedError as error:
            raise RuntimeError("Playwright could not open the local demo store") from error
        return await self._page.title()

    async def search(self, query: str) -> int:
        await self._page.locator("#search-input").fill(query)
        await self._page.locator("#search-button").click()
        await self._page.wait_for_selector(".product-card")
        return await self._page.locator(".product-card").count()

    async def apply_filters(self, max_price: float, min_rating: float) -> int:
        """Apply native ShopFlow filters and verify the rendered result count."""
        price_value = "500" if max_price <= 500 else "800" if max_price <= 800 else ""
        rating_value = "4.7" if min_rating >= 4.7 else "4.5" if min_rating >= 4.5 else ""
        await self._page.locator("#price-filter").select_option(price_value)
        await self._page.locator("#rating-filter").select_option(rating_value)
        await self._page.wait_for_timeout(100)
        return await self._page.locator(".product-card").count()

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
            await next_button.click()
            await self._page.wait_for_timeout(100)

    async def screenshot(self, name: str) -> str:
        path = self.screenshot_dir / f"{name}.png"
        await self._page.screenshot(path=str(path), full_page=True)
        return str(path)
