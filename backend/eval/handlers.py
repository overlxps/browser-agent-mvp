from datetime import date
from pathlib import Path

from backend.agent import (
    DeterministicShoppingAgent,
    OpenAICompatiblePlanner,
    TaskFlowAgent,
    TravelFlowAgent,
)
from backend.schemas import LLMSettings, RunRequest, TaskRunRequest, TravelRunRequest
from backend.tools import DemoStoreBrowser


def resolve_month(value: str) -> str:
    """Turn 'current'/'next' (or an explicit YYYY-MM) into a real month key."""
    if value and value not in {"current", "next"}:
        return value
    today = date.today().replace(day=1)
    offset = 1 if value == "next" else 0
    month_index = today.month - 1 + offset
    year = today.year + month_index // 12
    month = month_index % 12 + 1
    return f"{year}-{month:02d}"


class EvalHandlers:
    def __init__(
        self,
        shopflow_url: str,
        taskflow_url: str,
        travelflow_url: str,
        screenshot_dir: Path,
        llm_settings: LLMSettings,
    ) -> None:
        self.shopflow_url = shopflow_url
        self.taskflow_url = taskflow_url
        self.travelflow_url = travelflow_url
        self.screenshot_dir = screenshot_dir
        self.llm_settings = llm_settings

    def _shopflow_agent(self) -> DeterministicShoppingAgent:
        return DeterministicShoppingAgent(self.shopflow_url, self.screenshot_dir, OpenAICompatiblePlanner(self.llm_settings))

    def _payload_from_result(self, result) -> dict:
        return {
            "completed": result.completed,
            "products": [product.model_dump() for product in result.products],
            "hotels": [hotel.model_dump() for hotel in result.hotels],
            "recommendation": result.recommendation.model_dump() if result.recommendation else None,
            "updated_tasks": [task.model_dump() for task in result.updated_tasks],
            "detail": result.metadata.get("detail"),
            "done_count": result.metadata.get("done_count"),
            "all_in_progress": all(task.status == "in_progress" for task in result.updated_tasks) if result.updated_tasks else False,
            "step_count": len(result.steps),
            "retry_count": result.metadata.get("retry_count", 0),
            "model_calls": result.metadata.get("model_calls", 0),
            "failure_reasons": result.metadata.get("failure_reasons", []),
            "screenshot_path": result.metadata.get("screenshot_path") or (result.steps[-1].screenshot_path if result.steps else None),
            "category": result.metadata.get("category", ""),
        }

    async def shopflow_search(self, params: dict) -> dict:
        result = await self._shopflow_agent().run(RunRequest(**params))
        payload = self._payload_from_result(result)
        payload["products_price"] = [item["price"] for item in payload["products"]]
        payload["products_rating"] = [item["rating"] for item in payload["products"]]
        return payload

    async def shopflow_open_top_product(self, params: dict) -> dict:
        result = await self._shopflow_agent().open_top_product(params["product_id"])
        return self._payload_from_result(result)

    async def shopflow_category_extract(self, params: dict) -> dict:
        async with DemoStoreBrowser(self.shopflow_url, self.screenshot_dir) as browser:
            await browser.open_store()
            await browser.apply_filters(max_price=10000, min_rating=0, category=params["category"])
            products = await browser.extract_all_pages()
        return {
            "completed": True,
            "products": [product.model_dump() for product in products],
            "category": params["category"],
            "step_count": 4,
            "retry_count": 0,
            "model_calls": 0,
            "failure_reasons": [],
            "screenshot_path": None,
        }

    async def shopflow_detail(self, params: dict) -> dict:
        async with DemoStoreBrowser(self.shopflow_url, self.screenshot_dir) as browser:
            await browser.open_store()
            detail = await browser.open_product_detail(params["product_id"])
        return {
            "completed": True,
            "detail": detail,
            "step_count": 3,
            "retry_count": 0,
            "model_calls": 0,
            "failure_reasons": [],
            "screenshot_path": None,
        }

    async def shopflow_sort(self, params: dict) -> dict:
        async with DemoStoreBrowser(self.shopflow_url, self.screenshot_dir) as browser:
            await browser.open_store()
            await browser.search(params["query"])
            await browser.apply_sort(params["sort"])
            products = await browser.extract_products()
        trimmed = products[: params["limit"]]
        return {
            "completed": True,
            "products": [product.model_dump() for product in trimmed],
            "products_price": [product.price for product in trimmed],
            "step_count": 4,
            "retry_count": 0,
            "model_calls": 0,
            "failure_reasons": [],
            "screenshot_path": None,
        }

    async def taskflow_top_priority_update(self, params: dict) -> dict:
        result = await TaskFlowAgent(self.taskflow_url, self.screenshot_dir).run(TaskRunRequest(**params))
        return self._payload_from_result(result)

    async def taskflow_count_done(self, params: dict) -> dict:
        result = await TaskFlowAgent(self.taskflow_url, self.screenshot_dir).count_done_tasks()
        return self._payload_from_result(result)

    async def taskflow_overdue_update(self, params: dict) -> dict:
        reference = params.pop("today", None) or date.today().isoformat()
        result = await TaskFlowAgent(self.taskflow_url, self.screenshot_dir).run_overdue_update(TaskRunRequest(**params))
        payload = self._payload_from_result(result)
        payload["all_overdue"] = bool(payload["updated_tasks"]) and all(
            task["due_date"] < reference for task in payload["updated_tasks"]
        )
        return payload

    async def travelflow_search_weekend_hotel(self, params: dict) -> dict:
        params = dict(params)
        params["month"] = resolve_month(params.get("month", "current"))
        result = await TravelFlowAgent(self.travelflow_url, self.screenshot_dir).run(TravelRunRequest(**params))
        payload = self._payload_from_result(result)
        payload["hotels_price"] = [item["price"] for item in payload["hotels"]]
        payload["hotels_rating"] = [item["rating"] for item in payload["hotels"]]
        return payload

    async def travelflow_compare_two_hotels(self, params: dict) -> dict:
        params = dict(params)
        params["month"] = resolve_month(params.get("month", "current"))
        result = await TravelFlowAgent(self.travelflow_url, self.screenshot_dir).run(TravelRunRequest(**params))
        payload = self._payload_from_result(result)
        payload["has_recommendation"] = result.recommendation is not None
        return payload

    async def run_handler(self, handler: str, params: dict) -> dict:
        method = getattr(self, handler, None)
        if method is None:
            raise ValueError(f"未知 handler：{handler}")
        return await method(params)
