from pathlib import Path

from backend.schemas import Action, ActionType, Product, RunRequest, RunResult, StepLog
from backend.tools import DemoStoreBrowser
from backend.agent.planner import OpenAICompatiblePlanner


class DeterministicShoppingAgent:
    """A safe baseline: planner decisions are fixed, browser effects are real."""

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

    async def run(self, request: RunRequest) -> RunResult:
        steps: list[StepLog] = []
        max_steps = 6
        repeated_searches = 0

        def log(action: Action, observation: str, screenshot_path: str | None = None) -> None:
            steps.append(StepLog(step=len(steps) + 1, action=action, observation=observation, screenshot_path=screenshot_path))

        async with DemoStoreBrowser(self.store_url, self.screenshot_dir) as browser:
            decision = await self.planner.next_action("start", request, "尚未打开页面。")
            title = await browser.open_store()
            log(decision.action, f"已打开：{title}（规划来源：{decision.source}）")

            decision = await self.planner.next_action("opened", request, f"页面标题为 {title}。")
            count = await browser.search(request.query)
            log(
                decision.action,
                f"已搜索“{request.query}”，页面显示 {count} 个候选商品。（规划来源：{decision.source}）",
            )

            count = await browser.apply_filters(request.max_price, request.min_rating)
            screenshot = await browser.screenshot("after-filter")
            log(
                Action(type=ActionType.CLICK, reason="应用价格和评分筛选，并验证页面结果"),
                f"已应用价格 ≤ ¥{request.max_price:.0f}、评分 ≥ {request.min_rating:.1f}；当前页显示 {count} 个候选商品。",
                screenshot,
            )

            products: list[Product] = []
            phase = "searched"
            while len(steps) < max_steps:
                observation = (
                    f"当前搜索结果数量为 {count}，已提取商品数为 {len(products)}，"
                    f"重复搜索次数为 {repeated_searches}。"
                )
                decision = await self.planner.next_action(phase, request, observation)

                if decision.action.type == ActionType.FILL:
                    repeated_searches += 1
                    if repeated_searches > 1:
                        log(
                            Action(type=ActionType.EXTRACT_PRODUCTS, reason="重复搜索保护：页面未变化，改为读取现有结果"),
                            "检测到重复搜索，执行器拒绝重复操作并转入信息提取。",
                        )
                        products = await browser.extract_all_pages()
                        phase = "extracted"
                        continue
                    count = await browser.search(request.query)
                    log(decision.action, f"Agent 选择再次搜索，页面显示 {count} 个候选商品。（规划来源：{decision.source}）")
                    continue

                if decision.action.type == ActionType.EXTRACT_PRODUCTS:
                    products = await browser.extract_all_pages()
                    log(decision.action, f"已跨分页提取 {len(products)} 条结构化商品信息。（规划来源：{decision.source}）")
                    phase = "extracted"
                    continue

                if decision.action.type == ActionType.FINISH:
                    if not products:
                        products = await browser.extract_all_pages()
                        log(
                            Action(type=ActionType.EXTRACT_PRODUCTS, reason="完成前验证：必须先获得结构化页面数据"),
                            f"完成前验证通过：已提取 {len(products)} 条商品信息。",
                        )
                    log(decision.action, f"Agent 判断现有信息足够完成任务。（规划来源：{decision.source}）")
                    break

            if not products:
                products = await browser.extract_all_pages()
                log(
                    Action(type=ActionType.EXTRACT_PRODUCTS, reason="达到最大步骤数后的安全恢复"),
                    f"已达到 {max_steps} 步限制，提取当前页面的 {len(products)} 条商品信息。",
                )

        chosen = self.choose_products(products, request)
        if not steps or steps[-1].action.type != ActionType.FINISH:
            log(
                Action(type=ActionType.FINISH, reason="筛选完成，输出最终结果"),
                f"找到 {len(chosen)} 个满足价格 ≤ ¥{request.max_price:.0f} 且评分 ≥ {request.min_rating:.1f} 的商品。",
            )
        return RunResult(
            task=f"搜索 {request.query}，价格不高于 ¥{request.max_price:.0f}，评分不低于 {request.min_rating:.1f}",
            products=chosen,
            steps=steps,
            completed=True,
            message="任务完成。模型规划不可用时会自动使用安全回退策略。",
            metadata={"max_steps": max_steps, "allowed_origin": self.store_url, "guards": ["action allowlist", "repeat-search protection", "finish verification"]},
        )
