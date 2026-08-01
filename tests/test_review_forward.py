"""Tests del núcleo compartido de Shopee y Mercado Livre.

Hasta ahora solo se cubría de rebote, desde los tests de cada plataforma.
"""

import asyncio

import pytest

from src.links import MERCADOLIVRE_LINK_RE, SHOPEE_LINK_RE
from src.review_forward import (
    ReviewPipeline,
    build_review_message,
    drop_foreign_blocks,
    review_dedup_key,
)
from tests.fakes import FakeDedup

# Mensaje real de Crowman: dos productos de Amazon y uno de Mercado Livre.
MIXTO = (
    "Kit 12 Cuecas Boxer Reebok Microfibra Adulto Sem Costura\n"
    "🔥 R$ 94 em até 3x s/ juros\n"
    "🛒https://www.amazon.com.br/dp/B0CW25HCNG?tag=crowmantech-20\n"
    "\n"
    "Braé Essential Kit Fluido 260ml + Óleo Revival 60ml\n"
    "🔥 R$ 119,77 À vista\n"
    "🛒https://meli.la/19ZAxqR\n"
    "\n"
    "Kit 4 Bermuda Shorts Tactel Sandrini Elastano Academia Praia\n"
    "🔥 R$ 55 em até 2x s/ juros\n"
    "🛒https://www.amazon.com.br/dp/B0FFNRMR4L?tag=crowmantech-20\n"
    "\n"
    "🛍 Grupos de promos:\n"
    "https://ctlinks.com.br"
)


class FakePoster:
    def __init__(self, fail=False):
        self.posts = []
        self._fail = fail

    async def post(self, image, text):
        self.posts.append(text)

    async def post_text(self, text):
        if self._fail:
            raise RuntimeError("Telegram caído")
        self.posts.append(text)


def test_mixed_message_does_not_leak_amazon_products_to_the_ml_channel():
    """El canal de ML recibía los productos de Amazon —ya monetizados en su propio
    canal— con el tag de afiliado del competidor intacto."""
    msg = build_review_message(MIXTO, MERCADOLIVRE_LINK_RE, "[ML]", platform="ml")

    assert "meli.la/19ZAxqR" in msg
    assert "Braé Essential" in msg
    assert "amazon.com.br" not in msg
    assert "crowmantech-20" not in msg
    assert "Kit 12 Cuecas" not in msg


def test_footer_of_the_competitor_is_still_stripped():
    msg = build_review_message(MIXTO, MERCADOLIVRE_LINK_RE, "[ML]", platform="ml")
    assert "ctlinks.com.br" not in msg
    assert "Grupos de promos" not in msg


def test_message_starts_with_the_marker():
    msg = build_review_message(MIXTO, MERCADOLIVRE_LINK_RE, "[ML]", platform="ml")
    assert msg.startswith("[ML]\n\n")


def test_single_platform_message_survives_whole():
    text = "Fone Bluetooth\nR$ 49\nhttps://s.shopee.com.br/8V77TB32CU"
    msg = build_review_message(text, SHOPEE_LINK_RE, "[SH]", platform="shopee")
    assert "Fone Bluetooth" in msg
    assert "R$ 49" in msg
    assert "s.shopee.com.br/8V77TB32CU" in msg


def test_footer_of_giro_de_ofertas_is_stripped():
    """GIRO DE OFERTAS firma cada oferta con un link a su propio canal de Telegram
    (t.me/girodeofertas); sin este marcador, el reenvío manual de Shopee terminaría
    promocionando el canal competidor."""
    text = (
        "Bombom Ferrero Rocher Com 8 Unidades\n"
        "💰 Por R$23\n"
        "https://s.shopee.com.br/6fg0pPNtiC\n\n"
        "🛍 Todas as ofertas reunidas aqui:\n"
        "https://t.me/girodeofertas"
    )
    msg = build_review_message(text, SHOPEE_LINK_RE, "[SH]", platform="shopee")
    assert "Bombom Ferrero Rocher" in msg
    assert "Todas as ofertas reunidas aqui" not in msg
    assert "girodeofertas" not in msg


def test_block_without_links_is_kept_as_context():
    text = "⚡ OFERTAS DA SEMANA ⚡\n\nFone\nhttps://meli.la/AAA"
    msg = build_review_message(text, MERCADOLIVRE_LINK_RE, "[ML]", platform="ml")
    assert "OFERTAS DA SEMANA" in msg


def test_message_without_blank_lines_is_one_block_and_survives():
    """Sin separadores no hay forma de saber dónde termina un producto: se conserva."""
    text = "Fone https://meli.la/AAA e mouse https://www.amazon.com.br/dp/B0CW25HCNG"
    msg = build_review_message(text, MERCADOLIVRE_LINK_RE, "[ML]", platform="ml")
    assert "meli.la/AAA" in msg
    assert "amazon.com.br" in msg


def test_no_platform_means_no_filtering():
    kept = drop_foreign_blocks(MIXTO, MERCADOLIVRE_LINK_RE, ())
    assert kept == MIXTO


def test_returns_none_when_the_platform_has_no_links():
    assert build_review_message(MIXTO, SHOPEE_LINK_RE, "[SH]", platform="shopee") is None


def test_dedup_key_ignores_query_params_and_order():
    a = review_dedup_key("https://meli.la/B\nhttps://meli.la/A", MERCADOLIVRE_LINK_RE, "ml")
    b = review_dedup_key("https://meli.la/A?x=1\nhttps://meli.la/B", MERCADOLIVRE_LINK_RE, "ml")
    assert a == b == "ml:https://meli.la/A|https://meli.la/B"


def test_pipeline_claims_the_key_before_posting():
    poster, dedup = FakePoster(), FakeDedup()
    pipe = ReviewPipeline(
        poster,
        link_re=MERCADOLIVRE_LINK_RE,
        marker="[ML]",
        prefix="ml",
        platform="Mercado Livre",
        dedup=dedup,
    )
    text = "Fone\nhttps://meli.la/AAA"

    assert asyncio.run(pipe.handle(text)) == 1
    assert asyncio.run(pipe.handle(text)) == 1  # manejada, pero no republicada
    assert len(poster.posts) == 1


def test_pipeline_releases_the_key_when_posting_fails():
    """Un post fallido no debe dar la oferta por publicada: se reintenta."""
    poster, dedup = FakePoster(fail=True), FakeDedup()
    pipe = ReviewPipeline(
        poster,
        link_re=MERCADOLIVRE_LINK_RE,
        marker="[ML]",
        prefix="ml",
        platform="Mercado Livre",
        dedup=dedup,
    )
    text = "Fone\nhttps://meli.la/AAA"

    with pytest.raises(RuntimeError):
        asyncio.run(pipe.handle(text))
    assert dedup.keys == {}

    poster._fail = False
    assert asyncio.run(pipe.handle(text)) == 1
    assert len(poster.posts) == 1


def test_review_message_drops_foreign_block_whole_when_source_signs_it():
    """Guard: la firma del canal se limpia por su línea, no por su nombre suelto.

    El tag de afiliado ajeno (`iachadospromo-20`) vive DENTRO de la URL de Amazon. Un
    marcador ingenuo ("iachados") borraría esa línea de link y dejaría el nombre y el
    precio huérfanos, que `drop_foreign_blocks` conserva por ser un bloque sin links:
    basura de otra plataforma en el canal de Shopee.
    """
    text = (
        "Produto Shopee\n"
        "https://shopee.com.br/product/123/456\n\n"
        "Produto Amazon\n"
        "https://www.amazon.com.br/dp/B07QZB3PDY?tag=iachadospromo-20\n\n"
        "🛍️ IAchados"
    )
    msg = build_review_message(text, SHOPEE_LINK_RE, "MARCA", platform="shopee")

    assert msg is not None
    assert "IAchados" not in msg  # la firma se va
    assert "Produto Shopee" in msg  # lo nuestro queda
    assert "Produto Amazon" not in msg  # el bloque ajeno se va ENTERO, sin huérfanos
