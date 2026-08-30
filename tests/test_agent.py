from backend.agent.runner import DeterministicShoppingAgent
from backend.schemas import Product, RunRequest


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
