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


def test_variante_nativa_no_habla_de_recorte():
    """Con generacion 9:16 nativa no hay recorte posterior: la restriccion de
    'todo en la franja central' limitaria la composicion sin motivo."""
    normal = _generar_referencia("https://s.shopee.com.br/abc123")
    nativo = _generar_referencia("https://s.shopee.com.br/abc123 nativo", nativo=True)
    assert "recortado" in normal.prompt
    assert "recortado" not in nativo.prompt
    assert normal.prompt != nativo.prompt


def test_las_dos_variantes_sacan_el_texto():
    """Independiente del formato: el texto quemado molesta igual en los dos."""
    for nat in (False, True):
        ref = _generar_referencia("https://s.shopee.com.br/abc123", nativo=nat)
        assert "REMOVA todo o texto" in ref.prompt


def test_referencia_devuelve_el_link_del_producto():
    """Sin esto el link se pierde entre pedir la referencia y volver con el video."""
    ref = _generar_referencia("https://s.shopee.com.br/abc123")
    assert ref.link == "https://s.shopee.com.br/propio"


def test_las_dos_variantes_piden_narracion():
    """Sin esto hay que pedir la voz en una segunda vuelta, y cada vuelta gasta
    una generacion."""
    for nat in (False, True):
        ref = _generar_referencia("https://s.shopee.com.br/abc123", nativo=nat)
        assert "NARRAÇÃO" in ref.prompt
        assert "português do Brasil" in ref.prompt


def test_la_narracion_prohibe_inventar_datos():
    """El modelo no conoce precio ni plazos: si los narra, miente al comprador."""
    ref = _generar_referencia("https://s.shopee.com.br/abc123")
    assert "NÃO invente informações, preços" in ref.prompt


def test_reply_lleva_el_aviso_de_rango_para_lanny():
    """El aviso NO va dentro del caption: el post que se publica queda intacto y el
    precio anunciado es correcto (es el de partida). Va aparte, para que Lanny lo
    aclare hablando."""
    from dataclasses import dataclass
    from decimal import Decimal

    from src.post_generator_bot import BotReply

    r = BotReply(caption="post", photo_url="http://x", aviso="⚠️ hay variaciones")
    assert "variaciones" in r.aviso
    assert "variaciones" not in r.caption


# --- Personas en el video y objetos de uso -----------------------------------
#
# El prompt original prohibia "objetos novos" y a la vez pedia "o produto em uso":
# para una churrasqueira eso es imposible (la carne y el humo SON objetos nuevos),
# y el modelo devolvia el producto girando en el vacio. Son dos reglas distintas
# que estaban mezcladas en una: los objetos que el producto necesita para cumplir
# su funcion siempre van; las personas son una decision aparte, por comando.

_LINK = "https://s.shopee.com.br/abc123"


def test_por_defecto_no_muestra_personas():
    """El default se mantiene sin personas: las manos son lo que peor genera la IA."""
    ref = _generar_referencia(_LINK)
    assert "NÃO mostre pessoas" in ref.prompt
    assert "mãos" in ref.prompt


def test_modo_manos_permite_manos_pero_no_caras():
    ref = _generar_referencia(_LINK, personas="manos")
    assert "MÃOS" in ref.prompt
    assert "NÃO mostre rostos" in ref.prompt
    assert "NÃO mostre pessoas" not in ref.prompt


def test_modo_personas_permite_una_persona_sin_testimonio():
    """Una persona inventada hablando a camara se lee como testimonio falso."""
    ref = _generar_referencia(_LINK, personas="personas")
    assert "UMA pessoa adulta" in ref.prompt
    assert "depoimento" in ref.prompt


def test_ninos_prohibidos_en_las_tres_variantes():
    """Regla dura, no configurable: ningun modificador puede levantarla."""
    for modo in (None, "manos", "personas"):
        ref = _generar_referencia(_LINK, personas=modo)
        assert "NÃO mostre crianças ou bebês" in ref.prompt, modo


def test_siempre_permite_los_objetos_que_el_producto_necesita():
    """El bug que motivo el cambio: sin esto la parrilla sale sin carne ni humo."""
    for modo in (None, "manos", "personas"):
        for nativo in (False, True):
            ref = _generar_referencia(_LINK, personas=modo, nativo=nativo)
            assert "FUNCIONANDO" in ref.prompt, (modo, nativo)
            assert "objetos novos" not in ref.prompt, (modo, nativo)


def test_personas_y_nativo_se_combinan():
    """Son dos ejes independientes: formato y personas."""
    ref = _generar_referencia(_LINK, personas="manos", nativo=True)
    assert "MÃOS" in ref.prompt
    assert "recortado" not in ref.prompt


def test_las_reglas_compartidas_siguen_en_todas_las_variantes():
    """El refactor a bloques no debe perder nada del prompt original."""
    for modo in (None, "manos", "personas"):
        for nativo in (False, True):
            ref = _generar_referencia(_LINK, personas=modo, nativo=nativo)
            for esperado in ("REMOVA todo o texto", "NARRAÇÃO", "NÃO invente informações",
                             "NÃO mostre telefone", "10 segundos"):
                assert esperado in ref.prompt, (esperado, modo, nativo)


# --- Parseo de los modificadores del comando ---------------------------------

def test_modificadores_del_comando():
    """Antes el modo se detectaba con endswith("nativo"), que se rompe apenas hay
    dos modificadores: "/video <link> nativo manos" ya no termina en "nativo"."""
    from src.post_generator_bot import CON_MANOS, CON_PERSONAS, SIN_PERSONAS, leer_modificadores

    assert leer_modificadores(f"/video {_LINK}") == (False, SIN_PERSONAS)
    assert leer_modificadores(f"/video {_LINK} nativo") == (True, SIN_PERSONAS)
    assert leer_modificadores(f"/video {_LINK} manos") == (False, CON_MANOS)
    assert leer_modificadores(f"/video {_LINK} personas") == (False, CON_PERSONAS)
    # En cualquier orden, y sin importar mayusculas o acentos.
    assert leer_modificadores(f"/video {_LINK} nativo manos") == (True, CON_MANOS)
    assert leer_modificadores(f"/video {_LINK} MANOS nativo") == (True, CON_MANOS)
    assert leer_modificadores(f"/video {_LINK} mãos") == (False, CON_MANOS)


def test_una_palabra_cualquiera_no_activa_nada():
    """Si escribe algo que no es un modificador, vale el default: no se le puede
    colar una persona al video por una palabra suelta."""
    from src.post_generator_bot import SIN_PERSONAS, leer_modificadores

    assert leer_modificadores(f"/video {_LINK} porfa") == (False, SIN_PERSONAS)
