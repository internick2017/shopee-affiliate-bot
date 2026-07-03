from src.amazon_retagger import (
    build_amazon_post,
    extract_amazon_links,
    has_mercadolivre_links,
    retag_amazon_url,
)

TAG = "ofertaslanny-20"


def test_retag_replaces_existing_tag():
    url = "https://www.amazon.com.br/dp/B0F8BQ3KYW?tag=crowmantech-20"
    assert retag_amazon_url(url, TAG) == "https://www.amazon.com.br/dp/B0F8BQ3KYW?tag=ofertaslanny-20"


def test_retag_adds_tag_when_missing():
    url = "https://www.amazon.com.br/dp/B0F8BQ3KYW"
    assert retag_amazon_url(url, TAG) == "https://www.amazon.com.br/dp/B0F8BQ3KYW?tag=ofertaslanny-20"


def test_retag_preserves_other_params():
    url = "https://www.amazon.com.br/?linkCode=sl2&tag=crowmantech-20"
    assert retag_amazon_url(url, TAG) == "https://www.amazon.com.br/?linkCode=sl2&tag=ofertaslanny-20"


def test_extract_amazon_links():
    text = "Ofertaça 💵 R$ 19\nhttps://www.amazon.com.br/dp/B07QZB3PDY?tag=crowmantech-20\n\nanúncio"
    assert extract_amazon_links(text) == ["https://www.amazon.com.br/dp/B07QZB3PDY?tag=crowmantech-20"]


def test_extract_amazon_links_none():
    assert extract_amazon_links("https://meli.la/1ShxGBP só ML aqui") == []
    assert extract_amazon_links("") == []
    assert extract_amazon_links(None) == []


def test_has_mercadolivre_links():
    assert has_mercadolivre_links("https://meli.la/1ShxGBP") is True
    assert has_mercadolivre_links("veja em https://www.mercadolivre.com.br/x") is True
    assert has_mercadolivre_links("https://www.amazon.com.br/dp/x?tag=y") is False


def test_build_amazon_post_single_product():
    text = (
        "🔥 Placa de Video Nv RTX5060TI 8GB GDDR7 128BITS Ventus 2x OC Plus MSI 912-V536-023\n\n"
        "💵 R$ 2391\n"
        "https://www.amazon.com.br/dp/B0F8BQ3KYW?tag=crowmantech-20\n\n"
        "anúncio\n\n"
        "🛍 Grupos de promos:\n"
        "https://ctlinks.com.br"
    )
    expected = (
        "🔥 Placa de Video Nv RTX5060TI 8GB GDDR7 128BITS Ventus 2x OC Plus MSI 912-V536-023\n\n"
        "💵 R$ 2391\n"
        "https://www.amazon.com.br/dp/B0F8BQ3KYW?tag=ofertaslanny-20\n\n"
        "anúncio"
    )
    assert build_amazon_post(text, TAG) == expected


def test_build_amazon_post_skips_mercadolivre():
    text = (
        "Perfume Lattafa The Kingdom EDP 100ml\n\n"
        "De R$ 408 por R$ 167 no Pix\n"
        "https://meli.la/2NBCphd\n\n"
        "🛍 Grupos de promos:\nhttps://ctlinks.com.br"
    )
    assert build_amazon_post(text, TAG) is None


def test_build_amazon_post_no_links():
    assert build_amazon_post("Bom dia, sem ofertas", TAG) is None
