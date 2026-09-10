from datetime import date

from backend.agent.verifier import evaluate_check
from backend.eval.handlers import resolve_month
from backend.eval.runner import classify_failure


def test_count_equals_check():
    passed, _ = evaluate_check(
        {"name": "count", "type": "count_equals", "path": "products", "value": 2},
        {"products": [{"name": "a"}, {"name": "b"}]},
    )
    assert passed


def test_count_gte_check():
    passed, _ = evaluate_check(
        {"name": "count", "type": "count_gte", "path": "hotels", "value": 2},
        {"hotels": [{"price": 1}, {"price": 2}, {"price": 3}]},
    )
    assert passed


def test_sorted_asc_check():
    passed, _ = evaluate_check(
        {"name": "sort", "type": "sorted_asc", "path": "products", "field": "price"},
        {"products": [{"price": 199}, {"price": 269}]},
    )
    assert passed


def test_field_equals_check():
    passed, _ = evaluate_check(
        {"name": "stock", "type": "field_equals", "path": "detail.stock", "value": "12"},
        {"detail": {"stock": "12"}},
    )
    assert passed


def test_all_before_today_check():
    passed, _ = evaluate_check(
        {"name": "overdue", "type": "all_before_today", "path": "updated_tasks", "field": "due_date"},
        {"updated_tasks": [{"due_date": "2020-01-01"}, {"due_date": "2020-02-01"}]},
    )
    assert passed


def test_resolve_month_maps_relative_values():
    today = date.today()
    expected_current = f"{today.year}-{today.month:02d}"
    assert resolve_month("current") == expected_current
    assert resolve_month("2026-09") == "2026-09"
    # next 在 12 月时应当跨年
    assert resolve_month("next") != ""


def test_classify_failure_categories():
    assert classify_failure(ValueError("未找到选择器 #missing"), {}, False) == "页面定位失败"
    assert classify_failure(RuntimeError("playwright crashed"), {}, False) == "工具执行失败"
    assert classify_failure(None, {"completed": False}, False) == "任务验证失败"
    assert classify_failure(None, {"completed": True}, True) is None
