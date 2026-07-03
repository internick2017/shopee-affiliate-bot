from decimal import Decimal

import pytest

from src.models import Product
from src.shopee_client import MockShopeeClient, RealShopeeClient


def test_mock_returns_given_product():
    p = Product(
        item_id=1,
        shop_id=2,
        name="Dado",
        price_final=Decimal("10.00"),
        image_url="https://example.com/x.jpg",
        affiliate_link="https://s.shopee.com.br/GIVEN",
    )
    client = MockShopeeClient(product=p)
    assert client.fetch(2, 1) is p


def test_mock_default_product_has_affiliate_link():
    client = MockShopeeClient()
    product = client.fetch(shop_id=222, item_id=111)
    assert product.item_id == 111
    assert product.shop_id == 222
    assert product.affiliate_link != ""
    assert product.name != ""


def test_real_client_fetch_not_implemented():
    client = RealShopeeClient(app_id="x", secret="y")
    with pytest.raises(NotImplementedError):
        client.fetch(1, 2)
