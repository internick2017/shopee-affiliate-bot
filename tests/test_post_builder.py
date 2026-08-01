import random
from decimal import Decimal

from src.models import Product
from src.post_builder import (
    HookBank,
    build_post,
    build_price_block,
    format_brl,
)


def _product(**overrides):
    base = dict(
        item_id=111,
        shop_id=222,
        name="Saco De Lavar Tênis",
        price_final=Decimal("16.98"),
        image_url="https://example.com/img.jpg",
        affiliate_link="https://s.shopee.com.br/LANNY",
    )
    base.update(overrides)
    return Product(**base)


def test_format_brl_basic():
    assert format_brl(Decimal("16.90")) == "R$ 16,90"


def test_format_brl_thousands():
    assert format_brl(Decimal("1234.5")) == "R$ 1.234,50"


def test_price_block_plain():
    assert build_price_block(_product()) == "✅ Por: R$ 16,98 😱🛒"


def test_price_block_discount():
    p = _product(price_final=Decimal("16.90"), price_original=Decimal("35.00"))
    assert build_price_block(p) == "❌ De: R$ 35,00\n✅ Por: R$ 16,90 😱🛒"


def test_price_block_range():
    p = _product(price_final=Decimal("34.90"), is_price_range=True)
    assert build_price_block(p) == "✅ A partir de R$ 34,90 😱🛒"


def test_build_post_full_structure():
    post = build_post(_product(), hook="MAIS VENDIDO ❤️🔥")
    expected = (
        "MAIS VENDIDO ❤️🔥\n\n"
        "🛍️ Saco De Lavar Tênis\n\n"
        "✅ Por: R$ 16,98 😱🛒\n\n"
        "🛒 Compre aqui: https://s.shopee.com.br/LANNY\n\n"
        "⚠️ Promoção sujeita a alteração a qualquer momento."
    )
    assert post == expected


def test_hookbank_never_repeats_consecutively():
    random.seed(0)
    bank = HookBank(["A", "B", "C"])
    last = None
    for _ in range(50):
        current = bank.next()
        assert current != last
        last = current


def test_hookbank_single_hook_returns_it():
    bank = HookBank(["SOLO"])
    assert bank.next() == "SOLO"
    assert bank.next() == "SOLO"


def test_hookbank_empty_raises():
    import pytest

    with pytest.raises(ValueError):
        HookBank([])


def test_build_post_inserta_lineas_extra_despues_del_precio():
    producto = Product(
        item_id=0,
        shop_id=0,
        name="Kit Camisetas",
        price_final=Decimal("284.99"),
        image_url="",
        price_original=Decimal("625.29"),
        affiliate_link="https://ml/x",
    )

    post = build_post(producto, "GANCHO", extra_lines=("🏷️ 54% OFF no Pix",))

    assert "✅ Por: R$ 284,99 😱🛒\n🏷️ 54% OFF no Pix\n\n🛒 Compre aqui:" in post


def test_build_post_sin_extras_no_cambia():
    producto = Product(
        item_id=0,
        shop_id=0,
        name="Kit Camisetas",
        price_final=Decimal("284.99"),
        image_url="",
        affiliate_link="https://ml/x",
    )

    assert build_post(producto, "GANCHO") == build_post(producto, "GANCHO", extra_lines=())
    assert "🏷️" not in build_post(producto, "GANCHO")
