import pytest

from src.grabados_store import GrabadosStore, VideosStore

_HOY = 1_700_000_000


@pytest.fixture
def store(tmp_path):
    return VideosStore(tmp_path / "g.db")


def test_arranca_vacio(store):
    assert store.total() == 0
    assert store.ya_tiene_video(1, "nick") is False
    assert store.ids_del_canal("nick") == set()


def test_registrar_y_consultar(store):
    store.registrar(42, canal="nick", titulo="Teclado RGB")
    assert store.ya_tiene_video(42, "nick") is True
    assert store.total() == 1


def test_el_mismo_producto_puede_ir_a_los_dos_canales(store):
    """Nick y Lanny son cuentas de afiliado con audiencias distintas: grabar un
    producto para una no debe bloquearlo para la otra. Ya paso con la capa de
    colchao, entregada a las dos."""
    store.registrar(42, canal="nick", titulo="Capa de colchao")
    store.registrar(42, canal="lanny", titulo="Capa de colchao")
    assert store.total() == 2
    assert store.ya_tiene_video(42, "nick") is True
    assert store.ya_tiene_video(42, "lanny") is True


def test_un_canal_no_ve_los_del_otro(store):
    store.registrar(1, canal="nick")
    store.registrar(2, canal="lanny")
    assert store.ids_del_canal("nick") == {1}
    assert store.ids_del_canal("lanny") == {2}
    assert store.ya_tiene_video(2, "nick") is False


def test_regrabar_pisa_el_registro_anterior(store):
    """Lo que importa es el ultimo video entregado, no cada intento."""
    store.registrar(42, canal="nick", titulo="Primera", archivo="v1.mp4", now=_HOY)
    store.registrar(42, canal="nick", titulo="Segunda", archivo="v2.mp4", now=_HOY + 100)
    assert store.total() == 1
    assert store.listar()[0].archivo == "v2.mp4"


def test_comision_en_reais(store):
    """El numero con el que se elige que grabar: el porcentaje solo enganya."""
    store.registrar(1, canal="nick", precio=98.99, comision_pct=16.0)
    assert store.listar()[0].comision_reais == pytest.approx(15.8384)


def test_comision_en_reais_sin_datos_es_none(store):
    store.registrar(1, canal="nick")
    assert store.listar()[0].comision_reais is None


def test_listar_filtra_por_canal_y_ordena_por_fecha(store):
    store.registrar(1, canal="nick", titulo="Viejo", now=_HOY)
    store.registrar(2, canal="nick", titulo="Nuevo", now=_HOY + 100)
    store.registrar(3, canal="lanny", titulo="De Lanny", now=_HOY + 200)
    titulos = [v.titulo for v in store.listar(canal="nick")]
    assert titulos == ["Nuevo", "Viejo"]


def test_olvidar_es_por_canal(store):
    store.registrar(42, canal="nick")
    store.registrar(42, canal="lanny")
    assert store.olvidar(42, "nick") is True
    assert store.ya_tiene_video(42, "nick") is False
    assert store.ya_tiene_video(42, "lanny") is True
    assert store.olvidar(42, "nick") is False


def test_total_por_canal(store):
    store.registrar(1, canal="nick")
    store.registrar(2, canal="lanny")
    store.registrar(3, canal="lanny")
    assert store.total() == 3
    assert store.total("lanny") == 2


def test_convive_con_grabados_en_la_misma_base(tmp_path):
    """bot_generador filtra con GrabadosStore; VideosStore no debe interferir."""
    db = tmp_path / "g.db"
    videos, grabados = VideosStore(db), GrabadosStore(db)
    videos.registrar(1, canal="nick", titulo="Solo de Nick")
    assert grabados.grabados_todos() == set()
    grabados.marcar(2, titulo="De Lanny")
    assert grabados.grabados_todos() == {2}
    assert videos.total() == 1
