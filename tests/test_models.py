from decimal import Decimal

from src.models import Product


def _product(**overrides):
    base = dict(
        item_id=111,
        shop_id=222,
        name="Produto Teste",
        price_final=Decimal("16.90"),
        image_url="https://example.com/img.jpg",
    )
    base.update(overrides)
    return Product(**base)


def test_price_kind_plain_when_no_original():
    assert _product().price_kind == "plain"


def test_price_kind_discount_when_original_greater():
    p = _product(price_original=Decimal("35.00"))
    assert p.price_kind == "discount"


def test_price_kind_range_when_flagged():
    p = _product(is_price_range=True, price_original=Decimal("35.00"))
    assert p.price_kind == "range"


def test_price_kind_plain_when_original_not_greater():
    p = _product(price_original=Decimal("16.90"))
    assert p.price_kind == "plain"
