from pathlib import Path

from backend.agent.memory import AgentMemory
from backend.agent.planner import OpenAICompatiblePlanner
from backend.agent.recovery import RecoveryPolicy
from backend.agent.state_machine import AgentStateMachine
from backend.schemas import Action, ActionType, AgentRunResult, Product, RunRequest
from backend.tools import DemoStoreBrowser


class DeterministicShoppingAgent:
    """A safe baseline using the observe-execute-verify state machine."""

    def __init__(self, store_url: str, screenshot_dir: Path, planner: OpenAICompatiblePlanner) -> None:
        self.store_url = store_url
        self.screenshot_dir = screenshot_dir
        self.planner = planner

    @staticmethod
    def choose_products(products: list[Product], request: RunRequest) -> list[Product]:
        candidates = [
            product
            for product in products
            if product.price <= request.max_price and product.rating >= request.min_rating
        ]
        candidates.sort(key=lambda item: (-item.rating, item.price))
        chosen = candidates[: request.limit]
        for product in chosen:
            product.reason = f"评分 {product.rating:.1f}，价格 ¥{product.price:.0f}，符合你的筛选条件。"
        return chosen

    async def run(self, request: RunRequest) -> AgentRunResult:
        memory = AgentMemory()
        recovery = RecoveryPolicy(max_steps=10)

        async with DemoStoreBrowser(self.store_url, self.screenshot_dir) as browser:
            async def observe() -> str:
                count = await browser._page.locator(".product-card").count()
                return f"当前页面显示 {count} 个商品卡片"

            machine = AgentStateMachine(browser.executor, memory, recovery, observe, self.screenshot_dir)
            decision = await self.planner.next_action("start", request, "尚未打开页面。")
            machine.model_calls += 1 if decision.source == "llm" else 0
            await machine.run_action("打开 ShopFlow 商城", Action(type=ActionType.NAVIGATE, reason=decision.action.reason, value=self.store_url), planner_source=decision.source)

            decision = await self.planner.next_action("opened", request, "页面已打开。")
            machine.model_calls += 1 if decision.source == "llm" else 0
            await machine.run_action(
                f"搜索“{request.query}”",
                Action(type=ActionType.FILL, reason=decision.action.reason, selector="#search-input", value=request.query),
                planner_source=decision.source,
            )
            await machine.run_action("提交搜索", Action(type=ActionType.CLICK, reason="点击搜索", selector="#search-button"))
            await browser.apply_filters(request.max_price, request.min_rating)
            price_option = DemoStoreBrowser.price_option(request.max_price)
            rating_option = DemoStoreBrowser.rating_option(request.min_rating)
            if price_option:
                await machine.run_action(
                    f"应用价格 ≤ ¥{request.max_price:.0f} 筛选",
                    Action(type=ActionType.SELECT, reason="价格筛选", selector="#price-filter", value=price_option),
                )
            if rating_option:
                await machine.run_action(
                    f"应用评分 ≥ {request.min_rating:.1f} 筛选",
                    Action(type=ActionType.SELECT, reason="评分筛选", selector="#rating-filter", value=rating_option),
                )
            products = await browser.extract_all_pages()
            # Discrete filter options may be coarser than the request, so enforce exact bounds in Python.
            products = [
                product
                for product in products
                if product.price <= request.max_price and product.rating >= request.min_rating
            ]
            memory.remember("products", [product.model_dump() for product in products])
            await machine.run_action("跨页提取商品", Action(type=ActionType.EXTRACT, reason="提取商品", selector=".product-card"))
            await browser.screenshot(f"shopflow-final-{machine.run_id}")
            await machine.run_action("完成商品检索", Action(type=ActionType.FINISH, reason="完成"))

        chosen = self.choose_products(products, request)
        return AgentRunResult(
            task=f"搜索 {request.query}，价格不高于 ¥{request.max_price:.0f}，评分不低于 {request.min_rating:.1f}",
            products=chosen,
            steps=memory.steps,
            completed=True,
            message="任务完成。",
            metadata={
                "retry_count": recovery.total_retries,
                "model_calls": machine.model_calls,
                "failure_reasons": recovery.failure_reasons,
            },
        )

    async def open_top_product(self, product_id: str) -> AgentRunResult:
        memory = AgentMemory()
        recovery = RecoveryPolicy(max_steps=8)
        detail: dict[str, str] = {}

        async with DemoStoreBrowser(self.store_url, self.screenshot_dir) as browser:
            async def observe() -> str:
                return await browser._page.title()

            machine = AgentStateMachine(browser.executor, memory, recovery, observe, self.screenshot_dir)
            await machine.run_action("打开 ShopFlow", Action(type=ActionType.NAVIGATE, reason="打开", value=self.store_url))
            await machine.run_action(
                "打开商品详情页",
                Action(type=ActionType.CLICK, reason="打开详情", selector=f"[data-product-id='{product_id}']"),
            )
            detail = await browser.read_product_detail()
            memory.remember("detail", detail)
            await machine.run_action(
                "读取详情库存",
                Action(type=ActionType.EXTRACT, reason="提取库存", selector="#detail-content [data-field='stock']"),
            )
            await machine.run_action("完成详情读取", Action(type=ActionType.FINISH, reason="完成"))

        return AgentRunResult(
            task=f"打开商品 {product_id} 详情页",
            steps=memory.steps,
            completed=True,
            message=detail.get("name", ""),
            metadata={"detail": detail, "retry_count": recovery.total_retries},
        )
