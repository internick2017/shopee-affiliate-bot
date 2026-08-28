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


# --- referencia 9:16 para video -------------------------------------------------

def _jpeg_cuadrado(size=400, color=(180, 140, 90)) -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (size, size), color).save(buf, format="JPEG")
    return buf.getvalue()


def _generar_referencia(text, **kwargs):
    from src.post_generator_bot import generate_video_reference

    defaults = dict(
        http_get=_fake_get("https://shopee.com.br/produto-i.111.222"),
        http_post=_fake_post(_PRODUCT_OFFER_BODY),
        fetch_image=lambda url: _jpeg_cuadrado(),
    )
    defaults.update(kwargs)
    return generate_video_reference(text, "app", "secret", **defaults)


def test_referencia_devuelve_imagen_vertical():
    import io

    from PIL import Image

    ref = _generar_referencia("mira esto https://s.shopee.com.br/abc123")
    assert ref.error is None
    assert Image.open(io.BytesIO(ref.image_bytes)).size == (1080, 1920)


def test_referencia_separa_titulo_y_prompt():
    """Van separados porque juntos superan el tope de 1024 del caption."""
    ref = _generar_referencia("https://s.shopee.com.br/abc123")
    assert ref.caption == "Kit Panos de Limpeza"
    assert "10 segundos" in ref.prompt
    assert "NÃO mostre telefone" in ref.prompt
    assert len(ref.caption) <= 1024


def test_prompt_exige_producto_centrado():
    """El modo de reencuadre elegido recorta la franja central: lo que se va a
    los costados se pierde, asi que el video generado tiene que anticiparlo."""
    ref = _generar_referencia("https://s.shopee.com.br/abc123")
    assert "CENTRALIZADO" in ref.prompt
    assert "laterais" in ref.prompt or "lateral" in ref.prompt


def test_prompt_pide_sacar_el_texto_de_la_foto():
    ref = _generar_referencia("https://s.shopee.com.br/abc123")
    assert "REMOVA todo o texto" in ref.prompt


def test_referencia_sin_link_da_error():
    ref = _generar_referencia("hola, todo bien?")
    assert ref.image_bytes is None
    assert "link de Shopee" in ref.error


def test_referencia_sin_producto_da_error():
    ref = _generar_referencia(
        "https://s.shopee.com.br/abc123",
        http_post=_fake_post({"data": {"productOfferV2": {"nodes": []}}}),
    )
    assert ref.image_bytes is None
    assert ref.error


def test_referencia_si_falla_la_descarga_da_error():
    def explota(url):
        raise OSError("sin red")

    ref = _generar_referencia("https://s.shopee.com.br/abc123", fetch_image=explota)
    assert ref.image_bytes is None
    assert "foto" in ref.error


def test_referencia_no_exige_descuento():
    """Un producto sin descuento igual sirve para un video, a diferencia del post."""
    import copy

    body = copy.deepcopy(_PRODUCT_OFFER_BODY)
    body["data"]["productOfferV2"]["nodes"][0]["priceDiscountRate"] = 0
    ref = _generar_referencia("https://s.shopee.com.br/abc123", http_post=_fake_post(body))
    assert ref.error is None
    assert ref.image_bytes
