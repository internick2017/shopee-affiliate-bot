from decimal import Decimal

from src.mercadolivre_resolver import (
    MercadoLivreOffer,
    build_own_mercadolivre_links,
    extract_meli_shortlinks,
    has_meli_shortlinks,
    resolve_mercadolivre_item,
    resolve_mercadolivre_offer,
    resolve_mercadolivre_url,
    retag_mercadolivre_url,
)


def test_has_meli_shortlinks():
    assert has_meli_shortlinks("veja https://meli.la/1Q8EMBW agora")
    assert not has_meli_shortlinks("https://www.mercadolivre.com.br/social/x?ref=abc")
    assert not has_meli_shortlinks("")
    assert not has_meli_shortlinks(None)


def test_extract_meli_shortlinks():
    text = "a https://meli.la/AAA\nb https://meli.la/BBB"
    assert extract_meli_shortlinks(text) == [
        "https://meli.la/AAA",
        "https://meli.la/BBB",
    ]


# Body real (recortado) de una página /social/<afiliado>?ref=... resuelta, del tipo
# "compartir un producto puntual" — bajado durante la investigación del 2026-07-13.
_PRODUCT_BODY = (
    '<html><head>'
    '<meta property="og:title" content="Smart Tv Hisense De 65 Polegadas Vidaa 65u6qv Uled 4k"/>'
    '</head><body><script>window.__PRELOADED_STATE__={"melidataSocial":{'
    '"path":"/affiliates/profile","type":"view","should_ignore_stream":false,'
    '"event_data":{"page_type":"affiliate-profile","content_id":"not_apply",'
    '"item_id":"MLB54629493","owner_id":"2530242411","matt_tool":"70340356",'
    '"source":"affiliate-profile"}}}</script></body></html>'
)

# Body real (recortado) de un link que resuelve a una lista/colección, no a un
# producto puntual — sin melidataSocial.item_id.
_LIST_BODY = (
    '<html><head>'
    '<meta property="og:title" content="Minhas listas de recomendações"/>'
    '</head><body><script>window.__PRELOADED_STATE__={"page_type":"lists"}'
    '</script></body></html>'
)


# Body real (recortado) de un anuncio SIN ficha de catálogo, tipo "/up/{user_product_id}"
# — Polo Piquet Texturizada, item_id MLB7087251712, bajado el 2026-07-17. Confirmado a
# mano por Nick: la URL /up/MLBU4214169322 carga el producto real y trackea.
_UP_URL_BODY = (
    '<html><head>'
    '<meta property="og:title" content="Polo Piquet Texturizada Polo Wear"/>'
    '</head><body><script>window.__PRELOADED_STATE__={"melidataSocial":{'
    '"event_data":{"page_type":"affiliate-profile","item_id":"MLB7087251712"}},'
    '"polycards":[{"metadata":{"id":"MLB7087251712","user_product_id":"MLBU4214169322",'
    '"url":"www.mercadolivre.com.br\\u002Fpolo-piquet-texturizada-polo-wear'
    '\\u002Fup\\u002FMLBU4214169322"}}]'
    '}</script></body></html>'
)

# Body real (recortado) de un anuncio tipo "produto.mercadolivre.com.br/MLB-{id}-slug"
# — Kit Camisetas Tommy Hilfiger, item_id MLB5960042952, bajado el 2026-07-17.
# Confirmado a mano por Nick: carga el producto real y trackea.
_PRODUTO_URL_BODY = (
    '<html><head>'
    '<meta property="og:title" content="Kit Camisetas Tommy Hilfiger"/>'
    '</head><body><script>window.__PRELOADED_STATE__={"melidataSocial":{'
    '"event_data":{"page_type":"affiliate-profile","item_id":"MLB5960042952"}},'
    '"polycards":[{"metadata":{"id":"MLB5960042952","variation_id":"193307812783",'
    '"url":"produto.mercadolivre.com.br\\u002FMLB-5960042952-kit-camisetas'
    '-tommy-hilfiger-_JM"}}]'
    '}</script></body></html>'
)

# Body sintético con la URL envuelta en un deep-link de Adjust (ddnf.adj.st), como se
# observó en la investigación original del 2026-07-13 (Smart TV Hisense). El "id" acá
# se construyó igual al item_id a propósito, para aislar y probar el desenvolvimiento
# del deep-link en sí (en los datos reales, "id" y "product_id" pueden diferir del
# item_id — ver _PRODUCT_BODY para el caso donde no hay match y se cae al fallback).
_ADJST_WRAPPED_BODY = (
    '<html><head>'
    '<meta property="og:title" content="Smart Tv Hisense De 65 Polegadas"/>'
    '</head><body><script>window.__PRELOADED_STATE__={"melidataSocial":{'
    '"event_data":{"page_type":"affiliate-profile","item_id":"MLB54629493"}},'
    '"polycards":[{"metadata":{"id":"MLB54629493","product_id":"MLB54629493",'
    '"url":"ddnf.adj.st\\u002Fwebview\\u002F",'
    '"url_params":"?adj_campaign=social&adj_t=1y8rwb1z&url=https%3A%2F%2Fwww.'
    'mercadolivre.com.br%2Fsmart-tv-hisense-de-65-polegadas%2Fp%2FMLB54629493'
    '%3Fmatt_event_ts%3D123"}}]'
    '}</script></body></html>'
)


class _FakeResponse:
    def __init__(self, text):
        self.text = text
        self.closed = False

    def close(self):
        self.closed = True


def _fake_get(body):
    def get(url, **kwargs):
        return _FakeResponse(body)

    return get


def _boom(url, **kwargs):
    raise OSError("network down")


def test_resolve_url_uses_up_format_for_individual_listing():
    base_url = resolve_mercadolivre_url(
        "https://meli.la/1EfwXsp", http_get=_fake_get(_UP_URL_BODY)
    )
    assert base_url == (
        "https://www.mercadolivre.com.br/polo-piquet-texturizada-polo-wear"
        "/up/MLBU4214169322"
    )


def test_resolve_url_uses_produto_format_for_individual_listing():
    base_url = resolve_mercadolivre_url(
        "https://meli.la/1VHk77B", http_get=_fake_get(_PRODUTO_URL_BODY)
    )
    assert base_url == (
        "https://produto.mercadolivre.com.br"
        "/MLB-5960042952-kit-camisetas-tommy-hilfiger-_JM"
    )


def test_resolve_url_unwraps_adjst_deeplink():
    """El "url_params" original trae "%3Fmatt_event_ts%3D123" al final del "url="
    interno (tracking propio de ML) — _extract_canonical_url solo URL-decodea, no
    trunca query strings (ver design doc), así que el resultado los conserva. Es
    retag_mercadolivre_url, más abajo en el pipeline, quien los descarta al armar el
    link propio (ver test_retag_mercadolivre_url_strips_existing_query_and_fragment)."""
    base_url = resolve_mercadolivre_url(
        "https://meli.la/1Q8EMBW", http_get=_fake_get(_ADJST_WRAPPED_BODY)
    )
    assert base_url == (
        "https://www.mercadolivre.com.br/smart-tv-hisense-de-65-polegadas"
        "/p/MLB54629493?matt_event_ts=123"
    )


def test_resolve_url_falls_back_to_p_when_no_metadata_match():
    """_PRODUCT_BODY (fixture original, sin polycards) sigue cayendo al /p/{item_id}
    de siempre — mismo comportamiento que antes de este fix."""
    base_url = resolve_mercadolivre_url(
        "https://meli.la/1Q8EMBW", http_get=_fake_get(_PRODUCT_BODY)
    )
    assert base_url == "https://www.mercadolivre.com.br/p/MLB54629493"


def test_resolve_url_returns_none_for_list_page():
    assert (
        resolve_mercadolivre_url("https://meli.la/1Wn6zLc", http_get=_fake_get(_LIST_BODY))
        is None
    )


def test_resolve_url_returns_none_on_network_error():
    assert resolve_mercadolivre_url("https://meli.la/X", http_get=_boom) is None


def test_resolve_returns_item_id_for_product_page():
    item_id = resolve_mercadolivre_item(
        "https://meli.la/1Q8EMBW", http_get=_fake_get(_PRODUCT_BODY)
    )
    assert item_id == "MLB54629493"


def test_resolve_returns_none_for_list_page():
    """Un link de "lista" (no producto puntual) no trae item_id: sigue yendo a
    reenvío manual, no se inventa un producto."""
    item_id = resolve_mercadolivre_item(
        "https://meli.la/1Wn6zLc", http_get=_fake_get(_LIST_BODY)
    )
    assert item_id is None


def test_resolve_returns_none_on_network_error():
    """Un fallo de red no debe reventar el pipeline: el mensaje se descarta."""
    assert resolve_mercadolivre_item("https://meli.la/X", http_get=_boom) is None


def _body_with_item_id(item_id: str) -> str:
    return (
        '<html><body><script>window.__PRELOADED_STATE__={"melidataSocial":{'
        '"event_data":{"item_id":"' + item_id + '"}}}</script></body></html>'
    )


def test_resolve_accepts_well_formed_item_id():
    item_id = resolve_mercadolivre_item(
        "https://meli.la/X", http_get=_fake_get(_body_with_item_id("MLB12345"))
    )
    assert item_id == "MLB12345"


def test_resolve_rejects_empty_item_id():
    """Ya cubierto por el guard de `match.group(1)` vacío, pero el regex de formato
    también lo rechazaría: lo dejamos explícito acá."""
    item_id = resolve_mercadolivre_item(
        "https://meli.la/X", http_get=_fake_get(_body_with_item_id(""))
    )
    assert item_id is None


def test_resolve_rejects_malformed_item_id():
    """Un item_id con formato inesperado (acá, un fragmento de script inyectado) no
    debe terminar interpolado en la URL pública: se trata como fallo de resolución."""
    malformed = "<script>alert(1)</script>"
    item_id = resolve_mercadolivre_item(
        "https://meli.la/X", http_get=_fake_get(_body_with_item_id(malformed))
    )
    assert item_id is None


def test_retag_mercadolivre_url_builds_expected_link():
    url = retag_mercadolivre_url(
        "https://www.mercadolivre.com.br/p/MLB54629493", "lannybot", "56889681"
    )
    assert url == (
        "https://www.mercadolivre.com.br/p/MLB54629493"
        "?matt_word=lannybot&matt_tool=56889681"
    )


def test_retag_mercadolivre_url_strips_existing_query_and_fragment():
    """Una URL base que ya trae query/fragment propios de ML (tracking ajeno, no
    nuestro) los descarta en vez de mezclarlos con matt_word/matt_tool."""
    url = retag_mercadolivre_url(
        "https://www.mercadolivre.com.br/p/MLB54629493?matt_event_ts=123#foo",
        "lannybot",
        "56889681",
    )
    assert url == (
        "https://www.mercadolivre.com.br/p/MLB54629493"
        "?matt_word=lannybot&matt_tool=56889681"
    )


def test_build_own_links_all_resolve():
    text = "a https://meli.la/1Q8EMBW\nb https://meli.la/1Q8EMBW"
    resolved = build_own_mercadolivre_links(
        text, "lannybot", "56889681", http_get=_fake_get(_PRODUCT_BODY)
    )
    assert resolved == {
        "https://meli.la/1Q8EMBW": (
            "https://www.mercadolivre.com.br/p/MLB54629493"
            "?matt_word=lannybot&matt_tool=56889681"
        )
    }


def test_build_own_links_none_when_any_fails():
    """Todo-o-nada: dos links, uno resuelve y otro no -> el caller debe caer a
    reenvío manual, no publicar una mezcla."""
    calls = []

    def flaky_get(url, **kwargs):
        calls.append(url)
        body = _PRODUCT_BODY if url == "https://meli.la/AAA" else _LIST_BODY
        return _FakeResponse(body)

    text = "a https://meli.la/AAA\nb https://meli.la/BBB"
    assert build_own_mercadolivre_links(
        text, "lannybot", "56889681", http_get=flaky_get
    ) is None
    # Se corta apenas falla BBB: no sigue pidiendo links de más (no hay más acá, pero
    # confirma que no reintenta AAA ni pide nada fuera de los dos del texto).
    assert calls == ["https://meli.la/AAA", "https://meli.la/BBB"]


def test_build_own_links_none_without_shortlinks():
    assert (
        build_own_mercadolivre_links(
            "sem mercado livre aqui", "lannybot", "56889681", http_get=_boom
        )
        is None
    )


def test_build_own_links_resolves_each_shortlink_once():
    """Un mensaje multi-producto no debe pedir el mismo link dos veces."""
    calls = []

    def counting_get(url, **kwargs):
        calls.append(url)
        return _FakeResponse(_PRODUCT_BODY)

    text = "a https://meli.la/1Q8EMBW\nb https://meli.la/1Q8EMBW"
    build_own_mercadolivre_links(
        text, "lannybot", "56889681", http_get=counting_get
    )
    assert calls == ["https://meli.la/1Q8EMBW"]


class _ResponseWithBrokenClose:
    """Response cuyo close() levanta una excepción."""

    def __init__(self, text):
        self.text = text

    def close(self):
        raise RuntimeError("close() failed unexpectedly")


def _get_broken_close(url, **kwargs):
    return _ResponseWithBrokenClose(_PRODUCT_BODY)


def test_resolve_returns_none_when_close_raises():
    """Si close() levanta, debe devolver None y NO propagar la excepción."""
    item_id = resolve_mercadolivre_item(
        "https://meli.la/1Q8EMBW", http_get=_get_broken_close
    )
    assert item_id is None


def test_resolve_url_returns_none_when_close_raises():
    """Mismo caso que test_resolve_returns_none_when_close_raises, pero para
    resolve_mercadolivre_url (tiene su propio try/except, separado)."""
    assert (
        resolve_mercadolivre_url("https://meli.la/1Q8EMBW", http_get=_get_broken_close)
        is None
    )


# --- datos del producto (post propio) ---

# Recorte REAL de /social/<afiliado> para meli.la/1VHk77B, bajado el 2026-07-18.
# Nota: "components" es una lista de bloques tipados (así llega de verdad), no un dict
# con "title"/"price" como claves directas.
_POLYCARD_BODY = (
    '<html><body><script>window.__PRELOADED_STATE__={"melidataSocial":{'
    '"event_data":{"page_type":"affiliate-profile","item_id":"MLB5960042952"}},'
    '"polycards":[{"unique_id":"23534c1719f75a2ebc4",'
    '"metadata":{"id":"MLB5960042952",'
    '"url":"produto.mercadolivre.com.br\\u002FMLB-5960042952-kit-camisetas'
    '-tommy-hilfiger-chest-insert-brancapreta-2un-_JM"},'
    '"components":['
    '{"type":"title","id":"title","title":{'
    '"text":"Kit Camisetas Tommy Hilfiger Chest Insert Branca/preta 2un",'
    '"long_title":false}},'
    '{"type":"seller","id":"seller"},'
    '{"type":"price","id":"price","column":1,"price":{'
    '"previous_price":{"value":625.29,"currency":"BRL","decimal_style":"normal"},'
    '"current_price":{"value":284.99,"currency":"BRL","decimal_style":"superscript"},'
    '"discount_label":{"text":"54% OFF no Pix"}'
    '}}'
    ']}]}</script></body></html>'
)


def test_resolve_offer_devuelve_titulo_precio_y_descuento():
    offer = resolve_mercadolivre_offer(
        "https://meli.la/1VHk77B", http_get=_fake_get(_POLYCARD_BODY)
    )

    assert offer is not None
    assert offer.titulo == "Kit Camisetas Tommy Hilfiger Chest Insert Branca/preta 2un"
    assert offer.precio == Decimal("284.99")
    assert offer.precio_previo == Decimal("625.29")
    assert offer.descuento == "54% OFF no Pix"
    assert offer.url_canonica == (
        "https://produto.mercadolivre.com.br/MLB-5960042952-kit-camisetas"
        "-tommy-hilfiger-chest-insert-brancapreta-2un-_JM"
    )
    assert offer.tiene_descuento is True


def test_resolve_offer_sin_precio_previo_ni_etiqueta_no_tiene_descuento():
    body = _POLYCARD_BODY.replace(
        '"previous_price":{"value":625.29,"currency":"BRL","decimal_style":"normal"},',
        "",
    ).replace('"discount_label":{"text":"54% OFF no Pix"}', '"x":1')
    offer = resolve_mercadolivre_offer("https://meli.la/X", http_get=_fake_get(body))

    assert offer is not None
    assert offer.precio_previo is None
    assert offer.descuento is None
    assert offer.tiene_descuento is False


def test_resolve_offer_none_cuando_no_hay_item_id():
    assert resolve_mercadolivre_offer(
        "https://meli.la/X", http_get=_fake_get("pagina sin melidata")
    ) is None


def test_resolve_offer_none_cuando_no_hay_polycard():
    # el item_id resuelve pero no hay bloque de producto (ej. una pagina vieja/simple)
    assert resolve_mercadolivre_offer(
        "https://meli.la/X", http_get=_fake_get(_PRODUCT_BODY)
    ) is None


def test_resolve_offer_none_en_error_de_red():
    assert resolve_mercadolivre_offer("https://meli.la/X", http_get=_boom) is None


def test_resolve_offer_conserva_acentos_del_titulo():
    # la comilla dentro del titulo va ESCAPADA en el JSON real ( \" , dos
    # caracteres: backslash + comilla). El string de reemplazo de abajo la
    # escribe tal cual se vería en el JSON de verdad — si en vez de esto se
    # pusiera una comilla cruda, el fixture quedaría con JSON inválido, no
    # representaría el caso real que este test intenta cubrir.
    body = _POLYCARD_BODY.replace(
        "Kit Camisetas Tommy Hilfiger Chest Insert Branca/preta 2un",
        'Coração de Chocolate Ração 14\\" Premium',
    )
    offer = resolve_mercadolivre_offer("https://meli.la/X", http_get=_fake_get(body))

    assert offer is not None
    # tras el parseo, json.loads ya decodificó \" a una comilla literal
    assert offer.titulo == 'Coração de Chocolate Ração 14" Premium'


def test_resolve_offer_no_confunde_precio_de_cuotas_con_precio_real():
    # el precio total de las cuotas (299.99) vive mas adentro que el precio real
    # (284.99): si _buscar bajara antes de tiempo, tomaria el equivocado.
    body = _POLYCARD_BODY.replace(
        '"discount_label":{"text":"54% OFF no Pix"}',
        '"discount_label":{"text":"54% OFF no Pix"},'
        '"installments":{"values":[{"type":"price","price":{"value":299.99}}]}',
    )
    offer = resolve_mercadolivre_offer("https://meli.la/X", http_get=_fake_get(body))

    assert offer is not None
    assert offer.precio == Decimal("284.99")


# Polycard con metadata.url envuelta en un deep-link de Adjust (adj.st) sin desenvolver.
# Combina la estructura real de _POLYCARD_BODY (título, precio, descuento válidos) con
# el patrón real de adj.st-wrapped URL de _ADJST_WRAPPED_BODY. Propósito: probar que
# resolve_mercadolivre_offer degrada a None en lugar de devolver un url_canonica roto.
_POLYCARD_WITH_ADJST_URL_BODY = (
    '<html><body><script>window.__PRELOADED_STATE__={"melidataSocial":{'
    '"event_data":{"page_type":"affiliate-profile","item_id":"MLB5960042952"}},'
    '"polycards":[{"unique_id":"23534c1719f75a2ebc4",'
    '"metadata":{"id":"MLB5960042952",'
    '"url":"ddnf.adj.st\\u002Fwebview\\u002F",'
    '"url_params":"?adj_campaign=social&adj_t=1y8rwb1z&url=https%3A%2F%2Fwww.'
    'mercadolivre.com.br%2FMLB-5960042952-kit-camisetas-tommy-hilfiger%2Fp%2FMLB5960042952"},'
    '"components":['
    '{"type":"title","id":"title","title":{'
    '"text":"Kit Camisetas Tommy Hilfiger Chest Insert Branca/preta 2un",'
    '"long_title":false}},'
    '{"type":"seller","id":"seller"},'
    '{"type":"price","id":"price","column":1,"price":{'
    '"previous_price":{"value":625.29,"currency":"BRL","decimal_style":"normal"},'
    '"current_price":{"value":284.99,"currency":"BRL","decimal_style":"superscript"},'
    '"discount_label":{"text":"54% OFF no Pix"}'
    '}}'
    ']}]}</script></body></html>'
)


def test_resolve_offer_none_cuando_url_es_deeplink_sin_desenvolver():
    """Cuando metadata.url es un adj.st deep-link sin desenvolver, degradar a None en
    lugar de devolver un url_canonica roto. El caso es raro (49 links medidos el
    2026-07-18, zero adj.st en resolve_mercadolivre_offer), pero más seguro que
    publicar un link que no funciona."""
    offer = resolve_mercadolivre_offer(
        "https://meli.la/1VHk77B", http_get=_fake_get(_POLYCARD_WITH_ADJST_URL_BODY)
    )
    assert offer is None
