from pathlib import Path

from backend.agent.memory import AgentMemory
from backend.agent.recovery import RecoveryPolicy
from backend.agent.state_machine import AgentStateMachine
from backend.schemas import Action, ActionType, AgentRunResult, Hotel, TravelRunRequest
from backend.tools import TravelFlowBrowser


class TravelFlowAgent:
    def __init__(self, url: str, screenshot_dir: Path) -> None:
        self.url = url
        self.screenshot_dir = screenshot_dir

    @staticmethod
    def choose_recommendation(hotels: list[Hotel]) -> Hotel:
        ranked = sorted(hotels, key=lambda item: (-item.rating, item.price))
        recommended = ranked[0]
        recommended.reason = f"评分 {recommended.rating:.1f}，价格 ¥{recommended.price:.0f}，综合性价比最高。"
        return recommended

    async def run(self, request: TravelRunRequest) -> AgentRunResult:
        memory = AgentMemory()
        recovery = RecoveryPolicy(max_steps=14)
        recommendation_text = ""

        async with TravelFlowBrowser(self.url, self.screenshot_dir) as browser:

            async def observe() -> str:
                count = await browser._page.locator(".hotel-card").count()
                return f"当前显示 {count} 家酒店"

            machine = AgentStateMachine(browser.executor, memory, recovery, observe, self.screenshot_dir)

            await machine.run_action("打开 TravelFlow 酒店搜索页", Action(type=ActionType.NAVIGATE, reason="打开页面", value=self.url))
            await machine.run_action(
                f"选择 {request.month} 出行",
                Action(type=ActionType.SELECT, reason="选择月份", selector="#month-filter", value=request.month),
            )
            await machine.run_action(
                "筛选周末可订酒店" if request.weekend_only else "查看所有日期",
                Action(type=ActionType.SELECT, reason="出行类型筛选", selector="#weekend-filter", value="weekend" if request.weekend_only else "all"),
            )
            price_option = TravelFlowBrowser.price_option(request.max_price)
            if price_option:
                await machine.run_action(
                    f"筛选价格不超过 ¥{request.max_price:.0f}",
                    Action(type=ActionType.SELECT, reason="价格筛选", selector="#price-filter", value=price_option),
                )
            rating_option = TravelFlowBrowser.rating_option(request.min_rating)
            if rating_option:
                await machine.run_action(
                    f"筛选评分不低于 {request.min_rating}",
                    Action(type=ActionType.SELECT, reason="评分筛选", selector="#rating-filter", value=rating_option),
                )
            await machine.run_action("提交搜索并刷新结果", Action(type=ActionType.CLICK, reason="搜索", selector="#search-button"))
            await machine.run_action("等待页面渲染完成", Action(type=ActionType.WAIT, reason="等待渲染", value="200"))
            hotels = await browser.extract_hotels()
            # Discrete filter options may be coarser than the request, so enforce exact bounds in Python.
            hotels = [
                hotel
                for hotel in hotels
                if hotel.price <= request.max_price and hotel.rating >= request.min_rating and (not request.weekend_only or hotel.weekend_available)
            ]
            memory.remember("hotels", [hotel.model_dump() for hotel in hotels])
            await machine.run_action("提取酒店列表", Action(type=ActionType.EXTRACT, reason="提取酒店", selector=".hotel-card"))
            await machine.run_action("向下滚动查看比较区", Action(type=ActionType.SCROLL, reason="滚动", value="500"))
            if len(hotels) >= 2:
                recommendation_text = await browser.read_recommendation()
                memory.remember("recommendation_text", recommendation_text)
                await machine.run_action(
                    "读取推荐结果",
                    Action(type=ActionType.EXTRACT, reason="读取推荐", selector="[data-field='recommendation']"),
                )
            await browser.screenshot(f"travelflow-final-{machine.run_id}")
            await machine.run_action("完成酒店比较任务", Action(type=ActionType.FINISH, reason="任务完成"))

        trimmed = hotels[: request.limit]
        recommendation = self.choose_recommendation(trimmed) if trimmed else None
        return AgentRunResult(
            task=f"找 {request.limit} 家价格不高于 {request.max_price:.0f}、评分不低于 {request.min_rating} 的酒店并推荐一间",
            hotels=trimmed,
            recommendation=recommendation,
            steps=memory.steps,
            completed=True,
            message=recommendation_text or (recommendation.reason if recommendation else "没有符合条件的酒店。"),
            metadata={
                "retry_count": recovery.total_retries,
                "model_calls": machine.model_calls,
                "failure_reasons": recovery.failure_reasons,
                "screenshot_path": str(self.screenshot_dir / f"travelflow-final-{machine.run_id}.png"),
            },
        )
