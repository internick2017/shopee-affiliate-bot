"""Los mensajes son reales, de Crowman e IAchados. Cada uno rompe una regla distinta."""
from decimal import Decimal

from src.offers import extract_offers

TAGS = "?tag=crowmantech-20"

DOVE = (
    "O POBRE CUIDA DA SUA PELE 🤌\n\n"
    "Dove Sérum Hidratante 380ml\n"
    "- verifique se está disponível para sua região \n\n"
    "a partir de 28,39 à vista\n"
    f"Niacinamida + Uniformizador: https://www.amazon.com.br/dp/B0D8RHX3C6{TAGS}\n"
    f"Glicólico + Reparador de Textura: https://www.amazon.com.br/dp/B0GY9B1RQL{TAGS}\n"
    f"Pantenol + Dermo Reparador: https://www.amazon.com.br/dp/B0D8RG6QRD{TAGS}\n"
    f"Hialurônico + Dermo Renovador: https://www.amazon.com.br/dp/B0D9WXB99L{TAGS}\n"
)

DURACELL = (
    "PROS FELICIADE DOS CAIXISTA\n"
    "oferta exclusiva prime  \n\n"
    "pack 24un. Duracell Pilhas Alcalinas\n"
    "- compre em recorrência ( cancele quando quiser) \n"
    "- resgate o cupom de R$10 OFF do anuncio  \n\n"
    "84,67 à vista \n"
    f"AA Pequena: https://www.amazon.com.br/dp/B0C9RVFRZD{TAGS}\n"
    f"AAA Palito: https://www.amazon.com.br/dp/B0C9R8RC1P{TAGS}\n"
)

ELIXIR = (
    "TÁ DADO ESSE BLEND MENINAS ‼️\n\n"
    "E.lixir BEAUTYCOLOR Blend de 7 Óleos | Brilho e Luminosidade, 100ml\n"
    "🔥 R$ 18,80 À vista\n\n"
    f"🛒https://www.amazon.com.br/dp/B0DGMDDXL7{TAGS}\n\n"
    f"40ml - https://www.amazon.com.br/dp/B07H124PJL{TAGS}\n"
)

PS4 = (
    "🔥 Jogos de PS4 em Oferta\n\n"
    "🔹 The Last of Us - R$ 49\n"
    f"https://www.amazon.com.br/dp/B07L5BPDV7{TAGS}\n\n"
    "🔹 Bloodborne - R$ 54\n"
    f"https://www.amazon.com.br/dp/B07L4ZS23Q{TAGS}\n"
)

BRAE_MIXTO = (
    "Kit 12 Cuecas Boxer Reebok\n"
    "🔥 R$ 94 à vista\n"
    f"🛒https://www.amazon.com.br/dp/B0CW25HCNG{TAGS}\n\n"
    "Braé Essential Kit Fluido 260ml\n"
    "🔥 R$ 119,77 À vista\n"
    "🛒https://meli.la/19ZAxqR\n\n"
    "Kit 4 Bermuda Shorts Tactel\n"
    "🔥 R$ 55 em até 2x s/ juros\n"
    f"🛒https://www.amazon.com.br/dp/B0FFNRMR4L{TAGS}\n"
)

VITAFOR = (
    "PRA NÃO ESQUECER ONDE ESCONDEU O CONTROLE! 🤔\n\n"
    "🧠 Vitafor Omegafor Plus\n\n"
    "🔥 DE 378 | POR 97,49 - 240 Caps\n"
    "🔥 DE 154 | POR 46,08 - 120 Caps\n\n"
    "240 Caps\n"
    "🔗 https://www.amazon.com.br/dp/B07939CW22?th=1&psc=1&tag=iachadospromo-20\n"
    "120 Caps\n"
    "🔗 https://www.amazon.com.br/dp/B07939CW22?th=1&psc=1&tag=iachadospromo-20\n"
)

SIMPLE = (
    "🔥 Smirnoff Vodka 600Ml\n\n"
    "💵 R$ 19\n"
    f"https://www.amazon.com.br/dp/B07QZB3PDY{TAGS}\n"
)


def _asins(offers):
    return [o.url.split("/dp/")[1].split("?")[0] for o in offers]


# --- caso normal: un producto ---

def test_single_offer():
    offers = extract_offers(SIMPLE)
    assert len(offers) == 1
    assert offers[0].name == "Smirnoff Vodka 600Ml"
    assert offers[0].price_final == Decimal("19")
    assert offers[0].is_range is False


def test_no_offers_without_price():
    assert extract_offers(f"Produto legal\nhttps://www.amazon.com.br/dp/B07QZB3PDY{TAGS}") == []


def test_no_offers_without_amazon_link():
    assert extract_offers("Produto\n🔥 R$ 19\nhttps://meli.la/2E9VURp") == []


# --- variantes etiquetadas: un precio, varios links ---

def test_dove_variants_share_the_range_price():
    offers = extract_offers(DOVE)
    assert len(offers) == 4
    assert _asins(offers) == ["B0D8RHX3C6", "B0GY9B1RQL", "B0D8RG6QRD", "B0D9WXB99L"]
    assert all(o.price_final == Decimal("28.39") for o in offers)
    assert all(o.is_range for o in offers)  # "a partir de" -> "A partir de R$ ..."
    assert offers[0].name == "Dove Sérum Hidratante 380ml — Niacinamida + Uniformizador"
    assert offers[3].name == "Dove Sérum Hidratante 380ml — Hialurônico + Dermo Renovador"


def test_duracell_variants():
    offers = extract_offers(DURACELL)
    assert len(offers) == 2
    assert offers[0].name == "pack 24un. Duracell Pilhas Alcalinas — AA Pequena"
    assert offers[1].name == "pack 24un. Duracell Pilhas Alcalinas — AAA Palito"
    # el "cupom de R$10 OFF" no es el precio del producto
    assert all(o.price_final == Decimal("84.67") for o in offers)


# --- lo que NO se debe inferir ---

def test_elixir_second_link_has_no_price_and_is_dropped():
    """El link de 40ml no tiene precio propio: heredar los R$ 18,80 del 100ml sería mentir."""
    offers = extract_offers(ELIXIR)
    assert len(offers) == 1
    assert _asins(offers) == ["B0DGMDDXL7"]
    assert offers[0].price_final == Decimal("18.80")


def test_vitafor_same_asin_twice_yields_one_offer_at_the_first_price():
    """Los dos links son el MISMO ASIN con precios distintos: no hay forma de saber cuál variante."""
    offers = extract_offers(VITAFOR)
    assert len(offers) == 1
    assert _asins(offers) == ["B07939CW22"]
    assert offers[0].price_final == Decimal("97.49")
    assert offers[0].price_original == Decimal("378")


# --- nombre en la propia línea de precio ---

def test_ps4_names_come_from_the_price_line():
    offers = extract_offers(PS4)
    assert [o.name for o in offers] == ["The Last of Us", "Bloodborne"]
    assert [o.price_final for o in offers] == [Decimal("49"), Decimal("54")]
    assert _asins(offers) == ["B07L5BPDV7", "B07L4ZS23Q"]


def test_ps4_header_is_never_used_as_a_product_name():
    assert all("Jogos de PS4" not in o.name for o in extract_offers(PS4))


# --- mensaje mixto Amazon + Mercado Livre ---

def test_mixed_message_yields_only_the_amazon_offers():
    offers = extract_offers(BRAE_MIXTO)
    assert _asins(offers) == ["B0CW25HCNG", "B0FFNRMR4L"]


def test_ml_block_price_never_leaks_into_an_amazon_offer():
    offers = extract_offers(BRAE_MIXTO)
    assert Decimal("119.77") not in [o.price_final for o in offers]
    assert all("Braé" not in o.name for o in offers)
