from src.mercadolivre_resolver import (
    build_own_mercadolivre_links,
    extract_meli_shortlinks,
    has_meli_shortlinks,
    resolve_mercadolivre_item,
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


def test_retag_mercadolivre_url_builds_expected_link():
    url = retag_mercadolivre_url("MLB54629493", "lannybot", "56889681")
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
