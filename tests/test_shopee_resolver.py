import json
from decimal import Decimal

from src.shopee_resolver import (
    extract_shopee_shortlinks,
    resolve_shopee_offer,
    retag_shopee_url,
)

APP_ID = "test_app_id"
SECRET = "test_secret"


class _FakeResponse:
    """Simula tanto una respuesta de redirect (usa .url) como una respuesta de
    GraphQL (usa .status_code y .text/.json())."""

    def __init__(self, *, url=None, status_code=200, json_body=None):
        self.url = url
        self.status_code = status_code
        self._json_body = json_body or {}
        self.text = json.dumps(self._json_body)

    def json(self):
        return self._json_body

    def close(self):
        pass


def _fake_get(final_url):
    """Fake para seguir el redirect: siempre resuelve a `final_url`."""

    def get(url, **kwargs):
        return _FakeResponse(url=final_url)

    return get


def _fake_post(json_body, status_code=200):
    """Fake para la llamada POST a GraphQL."""

    def post(url, **kwargs):
        return _FakeResponse(status_code=status_code, json_body=json_body)

    return post


# Respuesta REAL de productOfferV2 (2026-07-18), producto real con descuento.
_PRODUCT_OFFER_BODY = {
    "data": {
        "productOfferV2": {
            "nodes": [
                {
                    "itemId": 23498094336,
                    "shopId": 860748832,
                    "productName": "Kit 10 Panos De Limpeza Microfibra alta absorção Multiuso",
                    "price": "16.88",
                    "priceDiscountRate": 83,
                    "commissionRate": "0.12",
                    "offerLink": "https://s.shopee.com.br/9pcpWfgiuH",
                }
            ]
        }
    }
}

# Respuesta REAL sin nodos (producto no en ninguna campaña de comisión).
_PRODUCT_OFFER_EMPTY = {"data": {"productOfferV2": {"nodes": []}}}

# Error REAL de la API (2026-07-18): link inválido/vencido.
_ERROR_INVALID_URL = {
    "errors": [
        {
            "message": "error [11001]: Params Error : invalid origin url",
            "path": ["generateShortLink"],
            "extensions": {"code": 11001, "message": "Params Error : invalid origin url"},
        }
    ]
}

# Respuesta REAL de generateShortLink (2026-07-18).
_GENERATE_SHORT_LINK_OK = {
    "data": {"generateShortLink": {"shortLink": "https://s.shopee.com.br/qi0pdhPjt"}}
}


def test_extract_shopee_shortlinks():
    text = "a https://s.shopee.com.br/AAA\nb https://shp.ee/BBB"
    assert extract_shopee_shortlinks(text) == [
        "https://s.shopee.com.br/AAA",
        "https://shp.ee/BBB",
    ]


def test_extract_shopee_shortlinks_vacio():
    assert extract_shopee_shortlinks(None) == []
    assert extract_shopee_shortlinks("sem shopee aqui") == []


def test_resolve_offer_formato_1_con_datos():
    # i.{shopId}.{itemId} - formato mas comun (49% de los links reales medidos)
    url_resuelta = "https://shopee.com.br/Kit-10-Panos-i.860748832.23498094336"
    offer = resolve_shopee_offer(
        "https://s.shopee.com.br/XXX",
        APP_ID,
        SECRET,
        http_get=_fake_get(url_resuelta),
        http_post=_fake_post(_PRODUCT_OFFER_BODY),
    )

    assert offer is not None
    assert offer.titulo == "Kit 10 Panos De Limpeza Microfibra alta absorção Multiuso"
    assert offer.precio == Decimal("16.88")
    assert offer.descuento_pct == 83
    assert offer.link_propio == "https://s.shopee.com.br/9pcpWfgiuH"
    assert offer.tiene_descuento is True
    # precio previo DERIVADO: 16.88 / (1 - 0.83) = 99.29 (verificado a mano)
    assert offer.precio_previo == Decimal("99.29")


def test_resolve_offer_formato_3_con_datos():
    # /{vendedor}/{shopId}/{itemId} - "nunca se cubrio" en el intento anterior,
    # es el 28% real de los links medidos - mismos datos, otra forma de URL.
    url_resuelta = "https://shopee.com.br/opaanlp/860748832/23498094336"
    offer = resolve_shopee_offer(
        "https://s.shopee.com.br/XXX",
        APP_ID,
        SECRET,
        http_get=_fake_get(url_resuelta),
        http_post=_fake_post(_PRODUCT_OFFER_BODY),
    )

    assert offer is not None
    assert offer.precio == Decimal("16.88")


def test_resolve_offer_sin_datos_de_producto():
    # la URL SI tiene forma de producto, pero productOfferV2 no tiene ese item
    url_resuelta = "https://shopee.com.br/Algo-i.999.888"
    offer = resolve_shopee_offer(
        "https://s.shopee.com.br/XXX",
        APP_ID,
        SECRET,
        http_get=_fake_get(url_resuelta),
        http_post=_fake_post(_PRODUCT_OFFER_EMPTY),
    )

    assert offer is None


def test_resolve_offer_url_no_es_producto():
    # cupon/VIP, carrito, etc - ni siquiera se llega a llamar productOfferV2
    llamadas = []

    def post_que_no_deberia_llamarse(url, **kwargs):
        llamadas.append(1)
        return _FakeResponse(json_body=_PRODUCT_OFFER_BODY)

    url_resuelta = "https://shopee.com.br/m/sabadovip"
    offer = resolve_shopee_offer(
        "https://s.shopee.com.br/XXX",
        APP_ID,
        SECRET,
        http_get=_fake_get(url_resuelta),
        http_post=post_que_no_deberia_llamarse,
    )

    assert offer is None
    assert llamadas == []  # no vale la pena llamar a la API para algo que no es producto


def test_resolve_offer_error_de_graphql():
    url_resuelta = "https://shopee.com.br/Kit-i.860748832.23498094336"
    offer = resolve_shopee_offer(
        "https://s.shopee.com.br/XXX",
        APP_ID,
        SECRET,
        http_get=_fake_get(url_resuelta),
        http_post=_fake_post(_ERROR_INVALID_URL),
    )

    assert offer is None


def test_resolve_offer_error_de_red():
    def get_roto(url, **kwargs):
        raise ConnectionError("boom")

    offer = resolve_shopee_offer(
        "https://s.shopee.com.br/XXX", APP_ID, SECRET, http_get=get_roto
    )

    assert offer is None


def test_resolve_offer_sin_descuento_no_es_oferta():
    body = json.loads(json.dumps(_PRODUCT_OFFER_BODY))  # copia
    body["data"]["productOfferV2"]["nodes"][0]["priceDiscountRate"] = 0
    url_resuelta = "https://shopee.com.br/Kit-i.860748832.23498094336"
    offer = resolve_shopee_offer(
        "https://s.shopee.com.br/XXX",
        APP_ID,
        SECRET,
        http_get=_fake_get(url_resuelta),
        http_post=_fake_post(body),
    )

    assert offer is not None
    assert offer.tiene_descuento is False


def test_resolve_offer_product_offer_null():
    # Regresión: GraphQL devuelve {"data": {"productOfferV2": null}} (null en vez
    # de ausente). Sin la guarda, data.get("productOfferV2", {}).get("nodes") falla
    # porque None.get() lanza AttributeError. Con la guarda (data.get(...) or {}),
    # degradamos seguramente a None.
    body = {"data": {"productOfferV2": None}}
    url_resuelta = "https://shopee.com.br/Kit-i.860748832.23498094336"
    offer = resolve_shopee_offer(
        "https://s.shopee.com.br/XXX",
        APP_ID,
        SECRET,
        http_get=_fake_get(url_resuelta),
        http_post=_fake_post(body),
    )

    assert offer is None


def test_retag_shopee_url_exito():
    link = retag_shopee_url(
        "https://shopee.com.br/m/sabadovip",
        APP_ID,
        SECRET,
        ["lannybot"],
        http_post=_fake_post(_GENERATE_SHORT_LINK_OK),
    )

    assert link == "https://s.shopee.com.br/qi0pdhPjt"


def test_retag_shopee_url_error():
    link = retag_shopee_url(
        "https://shopee.com.br/m/sabadovip",
        APP_ID,
        SECRET,
        [],
        http_post=_fake_post(_ERROR_INVALID_URL),
    )

    assert link is None


def test_retag_shopee_url_generate_short_link_null():
    # Regresión: GraphQL devuelve {"data": {"generateShortLink": null}} (null en vez
    # de ausente). Sin la guarda, data.get("generateShortLink", {}).get("shortLink") falla
    # porque None.get() lanza AttributeError. Con la guarda (data.get(...) or {}),
    # degradamos seguramente a None.
    body = {"data": {"generateShortLink": None}}
    link = retag_shopee_url(
        "https://shopee.com.br/m/sabadovip",
        APP_ID,
        SECRET,
        ["lannybot"],
        http_post=_fake_post(body),
    )

    assert link is None
