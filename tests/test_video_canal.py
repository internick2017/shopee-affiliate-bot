"""Regla de Nick (2026-10-13): el link de un video sale SIEMPRE de la cuenta del
canal donde se publica. `registrar_video` genera el link adentro, con las
credenciales del canal, en vez de aceptar uno que llega de afuera."""

from decimal import Decimal

import pytest

from src.grabados_store import VideosStore
from src.shopee_resolver import ShopeeOffer
from src.video_canal import credenciales, registrar_video

ENV = {
    "SHOPEE_APP_ID": "app-lanny", "SHOPEE_SECRET": "sec-lanny",
    "SHOPEE_APP_ID_NICK": "app-nick", "SHOPEE_SECRET_NICK": "sec-nick",
}


def oferta() -> ShopeeOffer:
    return ShopeeOffer(titulo="Capa de colchao", precio=Decimal("59.9"), descuento_pct=10,
                       comision_pct=Decimal("8"), link_propio="https://s.shopee.com.br/DE-OTRA-CUENTA",
                       item_id=42)


@pytest.fixture
def store(tmp_path):
    return VideosStore(tmp_path / "g.db")


def test_credenciales_por_canal():
    assert credenciales("nick", ENV) == ("app-nick", "sec-nick")
    assert credenciales("lanny", ENV) == ("app-lanny", "sec-lanny")


def test_sin_credenciales_del_canal_avisa_cual_falta():
    with pytest.raises(ValueError, match="SHOPEE_APP_ID_NICK"):
        credenciales("nick", {"SHOPEE_APP_ID": "x", "SHOPEE_SECRET": "y"})


def test_el_link_se_genera_con_las_credenciales_del_canal(store):
    llamadas = []

    def buscar_url(item_id, app_id, secret):
        llamadas.append(("url", item_id, app_id, secret))
        return "https://shopee.com.br/product/7/42"

    def retag(url, app_id, secret, subids):
        llamadas.append(("retag", url, app_id, secret, subids))
        return "https://s.shopee.com.br/NICK42"

    link = registrar_video(store, oferta(), canal="nick", herramienta="Flow", marca="@nickgranados",
                           archivo="capa.mp4", env=ENV, buscar_url=buscar_url, retag=retag)

    assert link == "https://s.shopee.com.br/NICK42"
    assert llamadas == [
        ("url", 42, "app-nick", "sec-nick"),
        ("retag", "https://shopee.com.br/product/7/42", "app-nick", "sec-nick", ["video", "nick"]),
    ]
    guardado = store.listar(canal="nick")[0]
    assert guardado.link == "https://s.shopee.com.br/NICK42"
    assert guardado.titulo == "Capa de colchao"
    assert guardado.precio == pytest.approx(59.9)


def test_si_no_se_puede_generar_el_link_no_registra_nada(store):
    with pytest.raises(RuntimeError, match="nick"):
        registrar_video(store, oferta(), canal="nick", herramienta="Flow", marca="@nickgranados",
                        archivo="capa.mp4", env=ENV,
                        buscar_url=lambda *_: "https://shopee.com.br/product/7/42", retag=lambda *_: None)
    assert store.listar(canal="nick") == []


def test_la_oferta_sin_item_id_no_se_puede_registrar(store):
    of = oferta()
    of.item_id = None
    with pytest.raises(ValueError, match="item_id"):
        registrar_video(store, of, canal="nick", herramienta="Flow", marca="@n", archivo="a.mp4", env=ENV)
