from decimal import Decimal

from src.prices import (
    extract_price,
    extract_price_info,
    is_coupon_line,
    is_price_line,
    parse_br_number,
)


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


# --- Promocasinha: precio con insignia de descuento ---


def test_price_line_with_discount_badge():
    """'Por: R$ 6,66 (44% off)' es un PRECIO con insignia, no una línea de cupón."""
    assert is_price_line("Por: R$ 6,66 (44% off)")
    assert is_price_line("Por: R$ 18,94 (39% OFF)")
    assert is_price_line("Por: R$ 66,51 à vista (40%OFF)")


def test_discount_badge_is_not_a_coupon_line():
    assert not is_coupon_line("Por: R$ 6,66 (44% off)")
    assert not is_coupon_line("Por: R$ 66,51 à vista (40%OFF)")


def test_coupon_line_still_detected_when_percent_comes_first():
    """El %OFF antes del precio sigue siendo cupón (post 'primeday' de IAchados)."""
    assert is_coupon_line("➡️ 10% OFF a partir de R$300, limitado a R$100 OFF")
    assert not is_price_line("➡️ 10% OFF a partir de R$300, limitado a R$100 OFF")


def test_extract_price_ignores_discount_badge_percentage():
    """El 44 de '(44% off)' no debe confundirse con el precio."""
    assert extract_price("Por: R$ 6,66 (44% off)") == (Decimal("6.66"), None)


# --- Crowman: "a partir de X" sin R$, y descuentos en R$ que no son precios ---


def test_a_partir_de_without_rs_is_a_price_line():
    """Crowman (Dove): 'a partir de 28,39 à vista'. Sin esto el mensaje se descarta entero."""
    assert is_price_line("a partir de 28,39 à vista")
    assert is_price_line("A partir de 28,39")
    assert is_price_line("A partir de: R$ 19,99")


def test_extract_price_info_flags_range():
    assert extract_price_info("a partir de 28,39 à vista") == (Decimal("28.39"), None, True)
    assert extract_price_info("A partir de: R$ 19,99") == (Decimal("19.99"), None, True)


def test_extract_price_info_not_range_for_plain_price():
    assert extract_price_info("🔥 R$ 183,82 parcelado") == (Decimal("183.82"), None, False)
    assert extract_price_info("De R$ 408 por R$ 167") == (Decimal("167"), Decimal("408"), False)


def test_rs_discount_amount_is_a_coupon_not_a_price():
    """Crowman (Duracell): '- resgate o cupom de R$10 OFF do anuncio' no es el precio."""
    assert is_coupon_line("- resgate o cupom de R$10 OFF do anuncio")
    assert not is_price_line("- resgate o cupom de R$10 OFF do anuncio")


def test_discount_badge_after_price_still_a_price():
    """No romper 'Por: R$ 6,66 (44% off)' al agregar la regla de R$X OFF."""
    assert is_price_line("Por: R$ 6,66 (44% off)")
    assert not is_coupon_line("Por: R$ 6,66 (44% off)")


def test_dot_with_two_decimals_is_not_a_thousands_separator():
    """ "99.90" es 99,90 en formato en-US. Tratarlo como miles lo multiplicaba por cien."""
    assert parse_br_number("99.90") == Decimal("99.90")
    assert parse_br_number("100.00") == Decimal("100.00")
    assert parse_br_number("1.23") == Decimal("1.23")


def test_dot_with_three_digits_is_still_a_thousands_separator():
    assert parse_br_number("2.391") == Decimal("2391")
    assert parse_br_number("1.234.567") == Decimal("1234567")


def test_comma_still_wins_as_decimal_separator():
    assert parse_br_number("1.289,10") == Decimal("1289.10")
    assert parse_br_number("99,90") == Decimal("99.90")


def test_coupon_ceiling_is_not_a_product_price():
    """ "Limite de R$ 50" es el tope del cupón; anclaba el nombre basura "Limite de"."""
    assert is_coupon_line("Limite de R$ 50")
    assert not is_price_line("Limite de R$ 50")
