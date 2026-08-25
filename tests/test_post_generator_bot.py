import json

from src.post_builder import HookBank
from src.post_generator_bot import generate_post_reply


class _FakeResponse:
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
    def get(url, **kwargs):
        return _FakeResponse(url=final_url)

    return get


def _fake_post(json_body, status_code=200):
    def post(url, **kwargs):
        return _FakeResponse(status_code=status_code, json_body=json_body)

    return post


_PRODUCT_OFFER_BODY = {
    "data": {
        "productOfferV2": {
            "nodes": [
                {
                    "productName": "Kit Panos de Limpeza",
                    "price": "16.88",
                    "priceDiscountRate": 83,
                    "commissionRate": "0.12",
                    "offerLink": "https://s.shopee.com.br/propio",
                    "imageUrl": "https://cf.shopee.com.br/file/abc",
                }
            ]
        }
    }
}


def test_generate_post_reply_con_link_valido():
    hooks = HookBank(["Hook único de teste"])
    get = _fake_get("https://shopee.com.br/produto-i.860748832.23498094336")
    post = _fake_post(_PRODUCT_OFFER_BODY)

    reply = generate_post_reply(
        "Mira esto: https://s.shopee.com.br/XXXX",
        "app_id",
        "secret",
        hooks,
        http_get=get,
        http_post=post,
    )

    assert reply.error is None
    assert reply.photo_url == "https://cf.shopee.com.br/file/abc"
    assert "Kit Panos de Limpeza" in reply.caption
    # Sin credenciales propias, el link del post es el que el usuario mandó, no el
    # offerLink de la cuenta por defecto — ver test_generate_post_reply_sin_credenciales_*.
    assert "https://s.shopee.com.br/XXXX" in reply.caption


def test_generate_post_reply_sin_link_de_shopee():
    hooks = HookBank(["Hook único de teste"])

    reply = generate_post_reply("hola, no hay link acá", "app_id", "secret", hooks)

    assert reply.caption is None
    assert reply.photo_url is None
    assert reply.error is not None


def test_generate_post_reply_producto_no_resuelve():
    hooks = HookBank(["Hook único de teste"])
    get = _fake_get("https://shopee.com.br/cart/")  # no tiene forma de producto

    reply = generate_post_reply(
        "https://s.shopee.com.br/XXXX", "app_id", "secret", hooks, http_get=get
    )

    assert reply.caption is None
    assert reply.error is not None


def test_generate_post_reply_sin_descuento():
    hooks = HookBank(["Hook único de teste"])
    body = json.loads(json.dumps(_PRODUCT_OFFER_BODY))
    body["data"]["productOfferV2"]["nodes"][0]["priceDiscountRate"] = 0
    get = _fake_get("https://shopee.com.br/produto-i.860748832.23498094336")
    post = _fake_post(body)

    reply = generate_post_reply(
        "https://s.shopee.com.br/XXXX",
        "app_id",
        "secret",
        hooks,
        http_get=get,
        http_post=post,
    )

    assert reply.caption is None
    assert reply.error is not None


def test_generate_post_reply_sin_credenciales_propias_devuelve_link_original():
    hooks = HookBank(["Hook único de teste"])
    get = _fake_get("https://shopee.com.br/produto-i.860748832.23498094336")
    post = _fake_post(_PRODUCT_OFFER_BODY)

    reply = generate_post_reply(
        "https://s.shopee.com.br/LINK_DO_DANIEL",
        "app_id_lanny",
        "secret_lanny",
        hooks,
        http_get=get,
        http_post=post,
    )

    assert reply.error is None
    # El link del post es el que Daniel mandó, NO el offerLink de la cuenta por
    # defecto (que la fixture pone en "https://s.shopee.com.br/propio").
    assert "https://s.shopee.com.br/LINK_DO_DANIEL" in reply.caption
    assert "https://s.shopee.com.br/propio" not in reply.caption


def test_generate_post_reply_con_credenciales_propias_usa_su_link():
    hooks = HookBank(["Hook único de teste"])
    body_propio = json.loads(json.dumps(_PRODUCT_OFFER_BODY))
    body_propio["data"]["productOfferV2"]["nodes"][0]["offerLink"] = (
        "https://s.shopee.com.br/LINK_PROPRIO_DO_DANIEL"
    )
    get = _fake_get("https://shopee.com.br/produto-i.860748832.23498094336")
    post = _fake_post(body_propio)

    reply = generate_post_reply(
        "https://s.shopee.com.br/LINK_QUE_DANIEL_MANDOU",
        "app_id_lanny",
        "secret_lanny",
        hooks,
        user_credentials=("app_id_daniel", "secret_daniel"),
        http_get=get,
        http_post=post,
    )

    assert reply.error is None
    assert "https://s.shopee.com.br/LINK_PROPRIO_DO_DANIEL" in reply.caption
    assert "https://s.shopee.com.br/LINK_QUE_DANIEL_MANDOU" not in reply.caption
