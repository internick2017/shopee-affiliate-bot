from decimal import Decimal

from src.lanny_post import _parse_br_number, extract_price, build_lanny_amazon_post

TAG = "ofertaslanny-20"


def test_parse_br_number():
    assert _parse_br_number("2391") == Decimal("2391")
    assert _parse_br_number("82,06") == Decimal("82.06")
    assert _parse_br_number("1.289,10") == Decimal("1289.10")
    assert _parse_br_number("2.391") == Decimal("2391")


def test_extract_price_single_rs():
    assert extract_price("💵 R$ 2391\nhttps://x") == (Decimal("2391"), None)


def test_extract_price_discount():
    assert extract_price("De R$ 408 por R$ 167 no Pix") == (Decimal("167"), Decimal("408"))


def test_extract_price_a_vista():
    assert extract_price("Jogo para Churrasco 12 pçs\n69,99 à vista\nhttps://x") == (Decimal("69.99"), None)


def test_extract_price_takes_first_of_two():
    assert extract_price("1.289,10 no pix\n1.449,00 em até 10x") == (Decimal("1289.10"), None)


def test_extract_price_none():
    assert extract_price("sem preço") == (None, None)


def test_build_lanny_amazon_post():
    text = (
        "🔥 Smirnoff Vodka 600Ml\n\n"
        "💵 R$ 19\n"
        "https://www.amazon.com.br/dp/B07QZB3PDY?tag=crowmantech-20\n\n"
        "anúncio\n\n"
        "🛍 Grupos de promos:\nhttps://ctlinks.com.br"
    )
    post = build_lanny_amazon_post(text, TAG, "MAIS VENDIDO ❤️🔥")
    expected = (
        "MAIS VENDIDO ❤️🔥\n\n"
        "🛍️ Smirnoff Vodka 600Ml\n\n"
        "✅ Por: R$ 19,00 😱🛒\n\n"
        "🛒 Compre aqui: https://www.amazon.com.br/dp/B07QZB3PDY?tag=ofertaslanny-20\n\n"
        "⚠️ Promoção sujeita a alteração a qualquer momento."
    )
    assert post == expected


def test_build_lanny_amazon_post_skips_mercadolivre():
    text = "Perfume X\n\nDe R$ 408 por R$ 167\nhttps://meli.la/2NBCphd"
    assert build_lanny_amazon_post(text, TAG, "GANCHO") is None


def test_build_lanny_amazon_post_no_amazon():
    assert build_lanny_amazon_post("Bom dia sem links", TAG, "GANCHO") is None


def test_build_lanny_amazon_post_iachados_de_por():
    text = (
        "COM ESSA MAIONESE, ATÉ O PÃO FICA CHIQUE DEMAIS! 😎\n\n"
        "🍔 Heinz Maionese Alho Tostado Com Ervas 215g\n\n"
        "🔥 DE 13,59 | POR 9,16\n"
        "🎟 CUPOM: MERCADO\n\n"
        "🔗 https://www.amazon.com.br/dp/B0B25NN5HL?th=1&psc=1&tag=iachadospromo-20\n\n"
        "🔹 Oferta exclusiva membros Amazon Prime.\n\n"
        "🛍️ IAchados"
    )
    post = build_lanny_amazon_post(text, TAG, "GANCHO")
    assert post is not None
    assert "Heinz Maionese Alho Tostado Com Ervas 215g" in post
    assert "R$ 9,16" in post
    assert "R$ 13,59" in post
    assert "tag=ofertaslanny-20" in post
    assert "iachadospromo-20" not in post


def test_build_lanny_amazon_post_iachados_primeday_is_none():
    text = (
        "ESSE DESCONTO É MELHOR QUE ACHADO EM GARAGEM!\n\n"
        "➡️ 10% OFF a partir de R$300, limitado a R$100 OFF\n"
        "🎟 cupom: PRIMEIRO\n\n"
        "🔗 https://www.amazon.com.br/primeday?tag=iachadospromo-20\n\n"
        "🛍️ IAchados"
    )
    assert build_lanny_amazon_post(text, TAG, "GANCHO") is None
