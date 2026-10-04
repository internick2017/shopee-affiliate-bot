"""El tiempo se inyecta con `now` para no depender del reloj ni esperar dias."""

import sqlite3

import pytest

from src.trend_store import Muestra, TrendStore

_DIA = 86400
_HOY = 1_700_000_000


@pytest.fixture
def store(tmp_path):
    return TrendStore(tmp_path / "t.db")


def _sembrar(store, item_id, muestras, **extra):
    """muestras = [(dias_atras, ventas), ...]"""
    for atras, ventas in muestras:
        store.registrar(item_id, ventas, now=_HOY - atras * _DIA, **extra)


def test_sin_datos_no_hay_tendencias(store):
    assert store.tendencias(now=_HOY) == []
    assert store.dias_con_datos() == 0


def test_un_solo_dia_no_alcanza(store):
    """Con una sola muestra no hay derivada que calcular."""
    _sembrar(store, 1, [(0, 1000)])
    assert store.dias_con_datos() == 1
    assert store.tendencias(now=_HOY) == []


def test_detecta_un_producto_que_crece(store):
    _sembrar(store, 1, [(6, 800), (0, 3000)], titulo="Despegando")
    r = store.tendencias(now=_HOY)
    assert len(r) == 1
    assert r[0].nuevas == 2200
    assert r[0].ventas_ahora == 3000


def test_ordena_por_crecimiento_relativo(store):
    """Un producto chico que duplica es mas interesante que un gigante estancado
    que suma lo mismo en absoluto."""
    _sembrar(store, 1, [(6, 1000), (0, 3000)], titulo="Chico que despega")   # +200%
    _sembrar(store, 2, [(6, 90000), (0, 92000)], titulo="Gigante estancado")  # +2%
    r = store.tendencias(now=_HOY)
    assert [t.titulo for t in r] == ["Chico que despega", "Gigante estancado"]


def test_filtra_el_ruido_de_bases_chicas(store):
    """Sin minimo, +2 ventas sobre una base de 3 aparece como +66%."""
    _sembrar(store, 1, [(6, 3), (0, 5)], titulo="Ruido")
    assert store.tendencias(now=_HOY) == []
    assert len(store.tendencias(now=_HOY, minimo_nuevas=1)) == 1


def test_ventas_por_dia(store):
    _sembrar(store, 1, [(10, 0), (0, 1000)])
    r = store.tendencias(now=_HOY, ventana_dias=30)
    assert r[0].dias == 10
    assert r[0].por_dia == 100


def test_ignora_lo_de_afuera_de_la_ventana(store):
    _sembrar(store, 1, [(60, 100), (0, 5000)], titulo="Viejo")
    assert store.tendencias(now=_HOY, ventana_dias=7) == []
    assert len(store.tendencias(now=_HOY, ventana_dias=90)) == 1


def test_dos_muestreos_el_mismo_dia_no_duplican(store):
    """La clave incluye el dia: correr el snapshot dos veces pisa, no duplica."""
    store.registrar(1, 100, now=_HOY)
    store.registrar(1, 150, now=_HOY + 3600)
    assert store.dias_con_datos() == 1
    _sembrar(store, 1, [(6, 50)])
    assert store.tendencias(now=_HOY)[0].ventas_ahora == 150


def test_crecimiento_pct_sin_dividir_por_cero(store):
    _sembrar(store, 1, [(6, 0), (0, 500)])
    assert store.tendencias(now=_HOY)[0].crecimiento_pct == 0.0


def test_conserva_datos_del_producto(store):
    _sembrar(store, 7, [(6, 100), (0, 900)], titulo="Kit X",
             precio=19.9, comision_pct=23.0, link="https://s.shopee.com.br/x")
    t = store.tendencias(now=_HOY)[0]
    assert (t.titulo, t.precio, t.comision_pct, t.link) == (
        "Kit X", 19.9, 23.0, "https://s.shopee.com.br/x")


def _filas_en_disco(tmp_path):
    """Lo que ve otro proceso: una conexion aparte solo lee lo ya escrito a disco."""
    otra = sqlite3.connect(tmp_path / "t.db")
    try:
        return otra.execute("SELECT COUNT(*) FROM ventas_diarias").fetchone()[0]
    finally:
        otra.close()


def test_una_tanda_queda_guardada_entera(store, tmp_path):
    store.registrar_muestras([Muestra(1, 10), Muestra(2, 20)], now=_HOY)
    assert _filas_en_disco(tmp_path) == 2


def test_una_tanda_con_una_muestra_rota_no_guarda_nada(store, tmp_path):
    with pytest.raises(sqlite3.IntegrityError):
        store.registrar_muestras([Muestra(1, 10), Muestra(2, None)], now=_HOY)
    assert _filas_en_disco(tmp_path) == 0


def test_una_tanda_vacia_no_rompe(store, tmp_path):
    store.registrar_muestras([], now=_HOY)
    assert _filas_en_disco(tmp_path) == 0


def test_las_ideas_se_publican_una_vez_por_dia(store):
    assert store.ideas_publicadas_hoy(now=_HOY) is False
    store.marcar_ideas_publicadas(now=_HOY)
    assert store.ideas_publicadas_hoy(now=_HOY + 3600) is True
    assert store.ideas_publicadas_hoy(now=_HOY + _DIA) is False
