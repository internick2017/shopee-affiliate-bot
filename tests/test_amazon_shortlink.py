import pytest

from src.amazon_shortlink import (
    expand_amazon_shortlinks,
    extract_amazon_shortlinks,
    has_amazon_shortlinks,
    resolve_amazon_shortlink,
)

PROMOCASINHA = (
    "Pilha Alcalina, Elgin, Palito AAA, Blister com 4\n"
    " \n"
    "Por: R$ 6,66\n"
    "\n"
    "Amazon:\n"
    "Compre em: https://link.amazon/B05ZZOGMH\n"
    "\n"
    "Promoção por tempo limitado."
)

# Lo que devuelve Amazon al seguir el redirect: producto real + tag y atribución AJENOS.
RESUELTA = (
    "https://www.amazon.com.br/dp/B0754J12RW"
    "?ascsubtag=srctok-0955edf0f424451f&btn_ref=srctok-6e9e13779b5839bc"
    "&th=1&linkCode=sl2&tag=amgbrt-20&linkId=f34c96e115c655ca5d42cacd10f49321"
)


class _FakeResponse:
    def __init__(self, url):
        self.url = url

    def close(self):
        pass


def _fake_get(final_url):
    def get(url, **kwargs):
        return _FakeResponse(final_url)

    return get


def _boom(url, **kwargs):
    raise OSError("network down")


def test_has_amazon_shortlinks():
    assert has_amazon_shortlinks(PROMOCASINHA)
    assert has_amazon_shortlinks("veja https://amzn.to/3xYz")
    assert not has_amazon_shortlinks("https://www.amazon.com.br/dp/B0F8BQ3KYW")
    assert not has_amazon_shortlinks("")
    assert not has_amazon_shortlinks(None)


def test_extract_amazon_shortlinks():
    assert extract_amazon_shortlinks(PROMOCASINHA) == ["https://link.amazon/B05ZZOGMH"]


def test_resolve_canonicalizes_to_dp_asin():
    """El path del shortlink NO es el ASIN: link.amazon/B05ZZOGMH -> dp/B0754J12RW."""
    url = resolve_amazon_shortlink(
        "https://link.amazon/B05ZZOGMH", http_get=_fake_get(RESUELTA)
    )
    assert url == "https://www.amazon.com.br/dp/B0754J12RW"


def test_resolve_drops_foreign_attribution():
    url = resolve_amazon_shortlink(
        "https://link.amazon/B05ZZOGMH", http_get=_fake_get(RESUELTA)
    )
    for rastro in ("amgbrt-20", "ascsubtag", "btn_ref", "linkId", "linkCode"):
        assert rastro not in url


def test_resolve_returns_none_when_no_asin():
    # redirect a la home (oferta caída), sin producto
    url = resolve_amazon_shortlink(
        "https://link.amazon/XXXX", http_get=_fake_get("https://www.amazon.com.br/")
    )
    assert url is None


def test_resolve_returns_none_on_network_error():
    """Un fallo de red no debe reventar el pipeline: el mensaje se descarta."""
    assert resolve_amazon_shortlink("https://link.amazon/X", http_get=_boom) is None


def test_expand_replaces_shortlink_in_text():
    out = expand_amazon_shortlinks(PROMOCASINHA, http_get=_fake_get(RESUELTA))
    assert "link.amazon" not in out
    assert "https://www.amazon.com.br/dp/B0754J12RW" in out
    # el resto del mensaje queda intacto
    assert "Pilha Alcalina, Elgin, Palito AAA, Blister com 4" in out
    assert "Por: R$ 6,66" in out


def test_expand_leaves_text_untouched_when_resolution_fails():
    out = expand_amazon_shortlinks(PROMOCASINHA, http_get=_boom)
    assert out == PROMOCASINHA


def test_expand_noop_without_shortlinks():
    text = "https://www.amazon.com.br/dp/B0F8BQ3KYW?tag=x-20"
    assert expand_amazon_shortlinks(text, http_get=_boom) == text


def test_expand_resolves_each_shortlink_once():
    """Un mensaje multi-producto no debe pedir el mismo link dos veces."""
    calls = []

    def counting_get(url, **kwargs):
        calls.append(url)
        return _FakeResponse(RESUELTA)

    text = "a https://link.amazon/AAA\nb https://link.amazon/AAA\nc https://link.amazon/BBB"
    expand_amazon_shortlinks(text, http_get=counting_get)
    assert sorted(calls) == [
        "https://link.amazon/AAA",
        "https://link.amazon/BBB",
    ]
