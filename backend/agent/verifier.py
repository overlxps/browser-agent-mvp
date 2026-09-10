from datetime import date
from typing import Any


def _get_path(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def evaluate_check(check: dict[str, Any], payload: dict[str, Any]) -> tuple[bool, str]:
    check_type = check["type"]
    if check_type == "equals":
        actual = _get_path(payload, check["path"])
        expected = check["value"]
        return actual == expected, f"期望 {expected}，实际 {actual}"
    if check_type == "count_equals":
        items = payload.get(check["path"], [])
        expected = check["value"]
        actual = len(items)
        return actual == expected, f"期望数量 {expected}，实际 {actual}"
    if check_type == "count_gte":
        items = payload.get(check["path"], [])
        expected = check["value"]
        actual = len(items)
        return actual >= expected, f"期望至少 {expected} 个，实际 {actual}"
    if check_type == "all_lte":
        field = check.get("field", "price")
        values = [item[field] for item in payload.get(check["path"], [])]
        limit = check["value"]
        return all(value <= limit for value in values), f"全部应 <= {limit}，实际 {values}"
    if check_type == "all_gte":
        field = check.get("field", "rating")
        values = [item[field] for item in payload.get(check["path"], [])]
        limit = check["value"]
        return all(value >= limit for value in values), f"全部应 >= {limit}，实际 {values}"
    if check_type == "all_before_today":
        field = check.get("field", "due_date")
        reference = check.get("value") or date.today().isoformat()
        values = [str(item[field]) for item in payload.get(check["path"], [])]
        if not values:
            return False, "没有可检查的项"
        return all(value < reference for value in values), f"全部应早于 {reference}，实际 {values}"
    if check_type == "sorted_asc":
        field = check.get("field", "price")
        values = [item[field] for item in payload.get(check["path"], [])]
        return values == sorted(values), f"顺序应为升序：{values}"
    if check_type == "field_equals":
        actual = _get_path(payload, check["path"])
        expected = check["value"]
        return actual == expected, f"期望 {expected}，实际 {actual}"
    if check_type == "completed":
        passed = bool(payload.get("completed"))
        return passed, "任务应标记为 completed"
    raise ValueError(f"未知断言类型：{check_type}")
