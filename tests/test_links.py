from src.links import (
    AMAZON_LINK_RE,
    MELI_SHORTLINK_RE,
    MERCADOLIVRE_LINK_RE,
    SHOPEE_LINK_RE,
    foreign_link_res,
    has_any_link,
)


def test_amazon_link_does_not_swallow_trailing_period():
    """`\\S+` se comía el punto de la frase y la URL quedaba rota."""
    assert AMAZON_LINK_RE.findall("veja https://www.amazon.com.br/dp/B07L5BPDV7. agora") == [
        "https://www.amazon.com.br/dp/B07L5BPDV7"
    ]


def test_amazon_link_does_not_swallow_closing_paren():
    assert AMAZON_LINK_RE.findall("(https://www.amazon.com.br/dp/B07L5BPDV7)") == [
        "https://www.amazon.com.br/dp/B07L5BPDV7"
    ]


def test_amazon_link_keeps_query_params():
    url = "https://www.amazon.com.br/dp/B07L5BPDV7?tag=x-20&th=1"
    assert AMAZON_LINK_RE.findall(f"oferta {url}") == [url]


def test_shopee_and_ml_links_drop_trailing_punctuation():
    assert SHOPEE_LINK_RE.findall("olha https://s.shopee.com.br/8V77TB32CU!") == [
        "https://s.shopee.com.br/8V77TB32CU"
    ]
    assert MERCADOLIVRE_LINK_RE.findall("olha https://meli.la/19ZAxqR,") == [
        "https://meli.la/19ZAxqR"
    ]


def test_foreign_link_res_excludes_own_platform():
    foreign = foreign_link_res("ml")
    assert MERCADOLIVRE_LINK_RE not in foreign
    assert AMAZON_LINK_RE in foreign
    assert SHOPEE_LINK_RE in foreign


def test_foreign_link_res_of_none_is_empty():
    assert foreign_link_res(None) == ()


def test_amazon_shortlink_counts_as_amazon_for_other_platforms():
    """Un `link.amazon/...` sin resolver sigue siendo un producto de Amazon."""
    assert has_any_link("https://link.amazon/B005pACpH", foreign_link_res("ml")) is True


def test_meli_shortlink_matches_only_short_form():
    assert MELI_SHORTLINK_RE.findall("olha https://meli.la/19ZAxqR,") == ["https://meli.la/19ZAxqR"]
    assert MELI_SHORTLINK_RE.findall("https://www.mercadolivre.com.br/social/x?ref=abc") == []
