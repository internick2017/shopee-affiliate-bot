import asyncio
import json
from decimal import Decimal

from src.shopee_review import (
    DEFAULT_MARKER,
    ShopeeReviewPipeline,
    build_shopee_auto_post,
    build_shopee_review_message,
    has_shopee_links,
    shopee_dedup_key,
)
from tests.fakes import FakeDedup


class FakePoster:
    def __init__(self):
        self.posts = []

    async def post_text(self, text):
        self.posts.append(text)


def test_has_shopee_links_detects_domains():
    assert has_shopee_links("veja https://s.shopee.com.br/30mAvLd6Uk agora")
    assert has_shopee_links("https://shopee.com.br/product/1/2")
    assert has_shopee_links("https://shp.ee/abc123")


def test_has_shopee_links_false():
    assert not has_shopee_links("https://www.amazon.com.br/dp/X")
    assert not has_shopee_links("")
    assert not has_shopee_links(None)


def test_build_shopee_review_message_none_without_shopee():
    assert build_shopee_review_message("sem shopee aqui") is None


def test_build_shopee_review_message_marks_and_keeps_links():
    text = (
        "📺 Smart TV 39\n"
        "🔥 POR 841,07 no Pix\n"
        "🔗 https://s.shopee.com.br/8V77TB32CU\n"
        "🔗 https://s.shopee.com.br/1VxN8JY0v7?lp=aff"
    )
    msg = build_shopee_review_message(text)
    assert msg.startswith(DEFAULT_MARKER)
    assert "https://s.shopee.com.br/8V77TB32CU" in msg
    assert "https://s.shopee.com.br/1VxN8JY0v7?lp=aff" in msg
    assert "Smart TV 39" in msg


def test_build_shopee_review_message_strips_competitor_footer():
    text = (
        "Produto X\n"
        "https://s.shopee.com.br/abc\n"
        "🛍 Grupos de promos:\n"
        "https://ctlinks.com.br"
    )
    msg = build_shopee_review_message(text)
    assert "ctlinks.com.br" not in msg
    assert "Grupos de promos" not in msg


def test_pipeline_posts_when_shopee():
    poster = FakePoster()
    pipe = ShopeeReviewPipeline(poster)
    n = asyncio.run(pipe.handle("🔗 https://s.shopee.com.br/abc"))
    assert n == 1
    assert len(poster.posts) == 1
    assert poster.posts[0].startswith(DEFAULT_MARKER)


def test_pipeline_skips_when_no_shopee():
    poster = FakePoster()
    pipe = ShopeeReviewPipeline(poster)
    n = asyncio.run(pipe.handle("https://www.amazon.com.br/dp/X"))
    assert n == 0
    assert poster.posts == []


# --- dedup ---


def test_shopee_dedup_key_ignores_query_params():
    a = shopee_dedup_key("🔗 https://s.shopee.com.br/8V77TB32CU")
    b = shopee_dedup_key("outro texto\n🔗 https://s.shopee.com.br/8V77TB32CU?lp=aff")
    assert a is not None and a == b


def test_shopee_dedup_key_none_without_links():
    assert shopee_dedup_key("sem shopee") is None


def test_shopee_dedup_key_differs_per_product():
    a = shopee_dedup_key("https://s.shopee.com.br/8V77TB32CU")
    b = shopee_dedup_key("https://s.shopee.com.br/2LWZxIxStA")
    assert a != b


def test_pipeline_skips_duplicate_shopee_offer():
    poster = FakePoster()
    dedup = FakeDedup()
    pipe = ShopeeReviewPipeline(poster, dedup=dedup)

    assert asyncio.run(pipe.handle("🔗 https://s.shopee.com.br/abc")) == 1
    assert len(poster.posts) == 1

    # mismo link, otro grupo, con query param extra
    assert asyncio.run(pipe.handle("outro\n🔗 https://s.shopee.com.br/abc?lp=aff")) == 1
    assert len(poster.posts) == 1


def test_pipeline_without_dedup_forwards_twice():
    poster = FakePoster()
    pipe = ShopeeReviewPipeline(poster)
    asyncio.run(pipe.handle("🔗 https://s.shopee.com.br/abc"))
    asyncio.run(pipe.handle("🔗 https://s.shopee.com.br/abc"))
    assert len(poster.posts) == 2


# --- post propio automático (Task 3) ---
#
# Los fakes de poster (FakePoster, con `post_text`) y de dedup (FakeDedup, importado
# de tests.fakes) ya están definidos/importados arriba en este archivo y se reusan acá
# tal cual — no se redefinen con otro nombre igual, porque una segunda definición de
# `class FakePoster`/`class FakeDedup` más abajo pisaría el nombre a nivel de módulo y
# rompería los tests preexistentes que dependen de esa interfaz (por ejemplo
# `FakePoster.post_text`, que es lo que `post_offer` llama cuando no hay foto).

APP_ID = "test_app_id"
SECRET = "test_secret"


class _FakeResponse:
    def __init__(self, *, url=None, status_code=200, json_body=None):
        self.url = url
        self.status_code = status_code
        self._json_body = json_body or {}

    def json(self):
        return self._json_body

    def close(self):
        pass


def _fake_get_por_link(mapa_url):
    """mapa_url: {shortlink: url_resuelta}. Cada shortlink resuelve a su propia URL."""

    def get(url, **kwargs):
        return _FakeResponse(url=mapa_url[url])

    return get


def _fake_post_por_query(respuestas):
    """respuestas: lista de dicts que se van devolviendo en orden, uno por llamada."""
    llamadas = {"n": 0}

    def post(url, **kwargs):
        resp = respuestas[llamadas["n"]]
        llamadas["n"] += 1
        return _FakeResponse(json_body=resp)

    return post


_PRODUCT_OFFER_BODY = {
    "data": {
        "productOfferV2": {
            "nodes": [
                {
                    "productName": "Kit 10 Panos De Limpeza Microfibra",
                    "price": "16.88",
                    "priceDiscountRate": 83,
                    "commissionRate": "0.12",
                    "offerLink": "https://s.shopee.com.br/9pcpWfgiuH",
                }
            ]
        }
    }
}

_GENERATE_SHORT_LINK_OK = {
    "data": {"generateShortLink": {"shortLink": "https://s.shopee.com.br/qi0pdhPjt"}}
}


def test_auto_post_un_producto_sin_extra():
    texto = "Kit de panos incrivel\nhttps://s.shopee.com.br/PRODUTO"
    msg = build_shopee_auto_post(
        texto,
        APP_ID,
        SECRET,
        hook="🔥 OFERTA!",
        http_get=_fake_get_por_link(
            {"https://s.shopee.com.br/PRODUTO": "https://shopee.com.br/x-i.860748832.23498094336"}
        ),
        http_post=_fake_post_por_query([_PRODUCT_OFFER_BODY]),
    )

    assert msg is not None
    assert "Kit 10 Panos De Limpeza Microfibra" in msg
    assert "R$ 16,88" in msg
    assert "83% OFF" in msg
    assert "s.shopee.com.br/9pcpWfgiuH" in msg
    assert "🎟️" not in msg  # sin link extra, sin linea de cupon


def test_auto_post_producto_mas_cupom():
    texto = (
        "Resgate aqui:\nhttps://s.shopee.com.br/CUPOM\n"
        "Kit de panos:\nhttps://s.shopee.com.br/PRODUTO"
    )
    msg = build_shopee_auto_post(
        texto,
        APP_ID,
        SECRET,
        hook="🔥 OFERTA!",
        http_get=_fake_get_por_link(
            {
                "https://s.shopee.com.br/CUPOM": "https://shopee.com.br/m/sabadovip",
                "https://s.shopee.com.br/PRODUTO": "https://shopee.com.br/x-i.860748832.23498094336",
            }
        ),
        http_post=_fake_post_por_query([_PRODUCT_OFFER_BODY, _GENERATE_SHORT_LINK_OK]),
    )

    assert msg is not None
    assert "🎟️" in msg
    assert "s.shopee.com.br/qi0pdhPjt" in msg


def test_auto_post_producto_mas_link_no_cupom_se_ignora():
    texto = (
        "Ve o carrinho:\nhttps://s.shopee.com.br/CARRINHO\n"
        "Kit de panos:\nhttps://s.shopee.com.br/PRODUTO"
    )
    msg = build_shopee_auto_post(
        texto,
        APP_ID,
        SECRET,
        hook="🔥 OFERTA!",
        http_get=_fake_get_por_link(
            {
                "https://s.shopee.com.br/CARRINHO": "https://shopee.com.br/cart/",
                "https://s.shopee.com.br/PRODUTO": "https://shopee.com.br/x-i.860748832.23498094336",
            }
        ),
        # solo UNA llamada esperada: productOfferV2. Nunca se llama generateShortLink
        # para el link de carrito, porque no matchea el patron de cupon.
        http_post=_fake_post_por_query([_PRODUCT_OFFER_BODY]),
    )

    assert msg is not None
    assert "🎟️" not in msg


def test_auto_post_solo_cupom_sin_producto():
    texto = "Ative o cupom:\nhttps://s.shopee.com.br/CUPOM"
    msg = build_shopee_auto_post(
        texto,
        APP_ID,
        SECRET,
        hook="🔥 OFERTA!",
        http_get=_fake_get_por_link(
            {"https://s.shopee.com.br/CUPOM": "https://shopee.com.br/m/sabadovip"}
        ),
        http_post=_fake_post_por_query([]),
    )

    assert msg is None


def test_auto_post_dos_productos_es_ambiguo():
    texto = (
        "https://s.shopee.com.br/PRODUTO1\n"
        "https://s.shopee.com.br/PRODUTO2"
    )
    msg = build_shopee_auto_post(
        texto,
        APP_ID,
        SECRET,
        hook="🔥 OFERTA!",
        http_get=_fake_get_por_link(
            {
                "https://s.shopee.com.br/PRODUTO1": "https://shopee.com.br/a-i.111.222",
                "https://s.shopee.com.br/PRODUTO2": "https://shopee.com.br/b-i.333.444",
            }
        ),
        http_post=_fake_post_por_query([_PRODUCT_OFFER_BODY, _PRODUCT_OFFER_BODY]),
    )

    assert msg is None


def test_auto_post_sin_hook_es_none():
    msg = build_shopee_auto_post(
        "https://s.shopee.com.br/PRODUTO", APP_ID, SECRET, hook=None
    )
    assert msg is None


def test_auto_post_retag_de_extra_falla_no_tumba_el_post():
    texto = (
        "https://s.shopee.com.br/CUPOM\n"
        "https://s.shopee.com.br/PRODUTO"
    )
    error = {"errors": [{"extensions": {"code": 11001}}]}
    msg = build_shopee_auto_post(
        texto,
        APP_ID,
        SECRET,
        hook="🔥 OFERTA!",
        http_get=_fake_get_por_link(
            {
                "https://s.shopee.com.br/CUPOM": "https://shopee.com.br/shopeevip",
                "https://s.shopee.com.br/PRODUTO": "https://shopee.com.br/x-i.860748832.23498094336",
            }
        ),
        http_post=_fake_post_por_query([_PRODUCT_OFFER_BODY, error]),
    )

    assert msg is not None  # el producto se publica igual
    assert "🎟️" not in msg  # pero sin la linea de cupon, que fallo


async def test_pipeline_auto_posts_cuando_configurado_y_resuelve():
    poster = FakePoster()
    pipe = ShopeeReviewPipeline(
        poster, dedup=FakeDedup(), app_id=APP_ID, secret=SECRET
    )

    import src.shopee_review as module

    original = module.build_shopee_auto_post

    def fake_build(text, app_id, secret, **kwargs):
        assert app_id == APP_ID
        assert secret == SECRET
        return "POST YA ARMADO"

    module.build_shopee_auto_post = fake_build
    try:
        result = await pipe.handle("https://s.shopee.com.br/XXX")
    finally:
        module.build_shopee_auto_post = original

    assert result == 1
    assert poster.posts == ["POST YA ARMADO"]


async def test_pipeline_sin_credenciales_cae_al_reenvio():
    poster = FakePoster()
    pipe = ShopeeReviewPipeline(poster, dedup=FakeDedup())  # sin app_id/secret

    text = "veja https://s.shopee.com.br/XXX"
    result = await pipe.handle(text)

    # sin credenciales, el reenvio marcado de siempre (no auto_post)
    assert result == 1
    assert "SHOPEE" in poster.posts[0]


# --- filtro por umbral de comision (Task 2) ---


def test_auto_post_bajo_umbral_de_comision_se_descarta():
    # mismo fixture de producto que ya usan los otros tests de este archivo, pero con
    # comision baja (3%, por debajo del umbral por defecto de 6%)
    body = json.loads(json.dumps(_PRODUCT_OFFER_BODY))
    body["data"]["productOfferV2"]["nodes"][0]["commissionRate"] = "0.03"

    texto = "Ar Condicionado\nhttps://s.shopee.com.br/PRODUTO"
    msg = build_shopee_auto_post(
        texto,
        APP_ID,
        SECRET,
        hook="🔥 OFERTA!",
        http_get=_fake_get_por_link(
            {"https://s.shopee.com.br/PRODUTO": "https://shopee.com.br/x-i.860748832.23498094336"}
        ),
        http_post=_fake_post_por_query([body]),
    )

    assert msg is None


def test_auto_post_en_o_sobre_el_umbral_publica():
    body = json.loads(json.dumps(_PRODUCT_OFFER_BODY))
    body["data"]["productOfferV2"]["nodes"][0]["commissionRate"] = "0.06"  # exacto en el umbral

    texto = "Kit de panos\nhttps://s.shopee.com.br/PRODUTO"
    msg = build_shopee_auto_post(
        texto,
        APP_ID,
        SECRET,
        hook="🔥 OFERTA!",
        http_get=_fake_get_por_link(
            {"https://s.shopee.com.br/PRODUTO": "https://shopee.com.br/x-i.860748832.23498094336"}
        ),
        http_post=_fake_post_por_query([body]),
    )

    assert msg is not None


def test_auto_post_umbral_personalizado_se_respeta():
    # comision 8%, pero con umbral custom de 10% deberia descartarse igual
    body = json.loads(json.dumps(_PRODUCT_OFFER_BODY))
    body["data"]["productOfferV2"]["nodes"][0]["commissionRate"] = "0.08"

    texto = "Producto\nhttps://s.shopee.com.br/PRODUTO"
    msg = build_shopee_auto_post(
        texto,
        APP_ID,
        SECRET,
        hook="🔥 OFERTA!",
        http_get=_fake_get_por_link(
            {"https://s.shopee.com.br/PRODUTO": "https://shopee.com.br/x-i.860748832.23498094336"}
        ),
        http_post=_fake_post_por_query([body]),
        umbral_comision=Decimal("10"),
    )

    assert msg is None
