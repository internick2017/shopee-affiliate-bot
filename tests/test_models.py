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
    """Sin descuento, el rango manda."""
    p = _product(is_price_range=True)
    assert p.price_kind == "range"


def test_price_kind_combina_descuento_y_rango():
    """CAMBIO DELIBERADO (2026-08-28): antes el rango pisaba al descuento y el post
    perdia el "De/Por", que es el gancho. Con 64 de 200 productos de Shopee teniendo
    las dos cosas, ahora se muestran juntas."""
    p = _product(is_price_range=True, price_original=Decimal("35.00"))
    assert p.price_kind == "discount_range"


def test_price_kind_plain_when_original_not_greater():
    p = _product(price_original=Decimal("16.90"))
    assert p.price_kind == "plain"
