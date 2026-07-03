import pytest

from src.shortlink_resolver import resolve_shortlink


class _FakeResponse:
    def __init__(self, url):
        self.url = url


def _fake_get(final_url):
    def _get(url, **kwargs):
        return _FakeResponse(final_url)
    return _get


def test_resolves_dash_i_pattern():
    final = "https://shopee.com.br/Produto-Legal-i.222.111?foo=bar"
    shop_id, item_id = resolve_shortlink(
        "https://s.shopee.com.br/AAA", http_get=_fake_get(final)
    )
    assert (shop_id, item_id) == (222, 111)


def test_resolves_product_path_pattern():
    final = "https://shopee.com.br/product/333/444"
    shop_id, item_id = resolve_shortlink(
        "https://s.shopee.com.br/BBB", http_get=_fake_get(final)
    )
    assert (shop_id, item_id) == (333, 444)


def test_raises_when_no_ids_found():
    final = "https://shopee.com.br/nada-por-aqui"
    with pytest.raises(ValueError):
        resolve_shortlink(
            "https://s.shopee.com.br/CCC", http_get=_fake_get(final)
        )
