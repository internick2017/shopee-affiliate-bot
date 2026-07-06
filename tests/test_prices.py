from decimal import Decimal

from src.prices import parse_br_number, is_coupon_line, is_price_line, extract_price


def test_parse_br_number():
    assert parse_br_number("2391") == Decimal("2391")
    assert parse_br_number("82,06") == Decimal("82.06")
    assert parse_br_number("1.289,10") == Decimal("1289.10")
    assert parse_br_number("2.391") == Decimal("2391")


def test_extract_price_discount_with_rs():
    # formato Crowman: "De R$ X por R$ Y"
    assert extract_price("De R$ 408 por R$ 167 no Pix") == (Decimal("167"), Decimal("408"))


def test_extract_price_discount_without_rs_iachados():
    # formato IAchados: "DE x | POR y" (sin R$, con pipe)
    assert extract_price("🔥 DE 13,59 | POR 9,16") == (Decimal("9.16"), Decimal("13.59"))
    assert extract_price("🔥 DE 139,88 | POR 52") == (Decimal("52"), Decimal("139.88"))


def test_extract_price_single_no_pix_iachados():
    assert extract_price("🔥 POR 841,07 no Pix") == (Decimal("841.07"), None)


def test_extract_price_single_rs():
    assert extract_price("💵 R$ 2391\nhttps://x") == (Decimal("2391"), None)


def test_extract_price_none():
    assert extract_price("sem preço") == (None, None)


def test_is_price_line_true_cases():
    assert is_price_line("💵 R$ 2391")
    assert is_price_line("28,99 à vista")
    assert is_price_line("🔥 DE 13,59 | POR 9,16")
    assert is_price_line("🔥 POR 841,07 no Pix")


def test_is_price_line_false_cases():
    assert not is_price_line("🍔 Heinz Maionese Alho Tostado Com Ervas 215g")
    assert not is_price_line("")
    # línea de cupón NO es ancla de precio (suprime falsos positivos "primeday")
    assert not is_price_line("➡️ 10% OFF a partir de R$300, limitado a R$100 OFF")


def test_is_coupon_line():
    assert is_coupon_line("10% OFF a partir de R$300")
    assert not is_coupon_line("R$ 19 no pix")


def test_extract_price_trailing_comma():
    assert extract_price("🔥 DE 13,59 | POR 9,16, corre!") == (Decimal("9.16"), Decimal("13.59"))
    assert extract_price("R$ 45,90, aproveite!") == (Decimal("45.90"), None)


def test_is_price_line_not_confused_by_de_por_words():
    assert not is_price_line("de 5 estrelas")
    assert not is_price_line("De 10 a 20 de julho")
    assert is_price_line("🔥 DE 13,59 | POR 9,16")
    assert is_price_line("🔥 POR 841,07 no Pix")
