from backend.agent.runner import DeterministicShoppingAgent
from backend.agent.taskflow import TaskFlowAgent
from backend.schemas import Product, RunRequest, TaskItem
from backend.tools import DemoStoreBrowser, TravelFlowBrowser


def test_choose_products_filters_and_sorts():
    products = [
        Product(name="C", price=200, rating=4.5, url="https://example.test/c"),
        Product(name="A", price=499, rating=4.8, url="https://example.test/a"),
        Product(name="B", price=300, rating=4.7, url="https://example.test/b"),
        Product(name="Too expensive", price=600, rating=5.0, url="https://example.test/d"),
    ]
    request = RunRequest(query="耳机", max_price=500, min_rating=4.5, limit=2)
    result = DeterministicShoppingAgent.choose_products(products, request)
    assert [product.name for product in result] == ["A", "B"]
    assert all(product.reason for product in result)


def test_price_option_picks_smallest_superset():
    # 420 元预算介于 300 与 500 之间，页面档位必须放宽到 500 才能覆盖候选
    assert DemoStoreBrowser.price_option(420) == "500"
    assert DemoStoreBrowser.price_option(300) == "300"
    assert DemoStoreBrowser.price_option(800) == "800"
    # 超过最高档位时不设页面筛选，由 Python 精确复筛
    assert DemoStoreBrowser.price_option(950) == ""


def test_rating_option_picks_largest_subset():
    # 4.6 分要求介于 4.5 与 4.7 之间，页面档位必须收窄到 4.5 才是超集
    assert DemoStoreBrowser.rating_option(4.6) == "4.5"
    assert DemoStoreBrowser.rating_option(4.7) == "4.7"
    assert DemoStoreBrowser.rating_option(4.0) == ""


def test_hotel_threshold_options():
    assert TravelFlowBrowser.price_option(700) == "800"
    assert TravelFlowBrowser.price_option(1500) == ""
    assert TravelFlowBrowser.rating_option(4.5) == "4.5"
    assert TravelFlowBrowser.rating_option(4.3) == ""


def test_filter_overdue_only_includes_past_todo():
    tasks = [
        TaskItem(id="a", title="过期待办", priority="high", due_date="2020-01-01", status="todo"),
        TaskItem(id="b", title="未过期", priority="high", due_date="2999-01-01", status="todo"),
        TaskItem(id="c", title="过期已完成", priority="high", due_date="2020-01-01", status="done"),
    ]
    overdue = TaskFlowAgent.filter_overdue(tasks, today="2026-09-01")
    assert [task.id for task in overdue] == ["a"]
