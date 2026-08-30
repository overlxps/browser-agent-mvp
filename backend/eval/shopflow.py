from time import perf_counter

from backend.schemas import RunRequest


SHOPFLOW_UNDER_BUDGET = RunRequest(
    query="无线耳机",
    max_price=500,
    min_rating=4.5,
    limit=3,
)


async def evaluate_shopflow(agent) -> dict:
    """A runnable task contract, not a screenshot-only demo assertion."""
    started_at = perf_counter()
    result = await agent.run(SHOPFLOW_UNDER_BUDGET)
    criteria = [
        len(result.products) == 3,
        all(item.price <= SHOPFLOW_UNDER_BUDGET.max_price for item in result.products),
        all(item.rating >= SHOPFLOW_UNDER_BUDGET.min_rating for item in result.products),
        result.completed,
    ]
    return {
        "task_id": "shopflow-under-budget-v1",
        "passed": all(criteria),
        "duration_ms": round((perf_counter() - started_at) * 1000),
        "step_count": len(result.steps),
        "returned_product_count": len(result.products),
        "checks": {
            "returns_exactly_three": criteria[0],
            "respects_price_limit": criteria[1],
            "respects_rating_limit": criteria[2],
            "agent_completed": criteria[3],
        },
    }
