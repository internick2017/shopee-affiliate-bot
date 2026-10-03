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


def test_arranca_sin_publicar(store):
    store.registrar(1, canal="nick")
    v = store.listar()[0]
    assert v.publicado is False
    assert v.publicado_ts is None
    assert v.dias_publicado is None


def test_marcar_publicado(store):
    store.registrar(1, canal="nick")
    assert store.marcar_publicado(1, "nick", cuando=_HOY) is True
    v = store.listar()[0]
    assert v.publicado is True
    assert v.publicado_ts == _HOY


def test_marcar_publicado_de_un_video_inexistente(store):
    assert store.marcar_publicado(999, "nick") is False


def test_publicar_es_por_canal(store):
    store.registrar(1, canal="nick")
    store.registrar(1, canal="lanny")
    store.marcar_publicado(1, "nick", cuando=_HOY)
    porcanal = {v.canal: v.publicado for v in store.listar()}
    assert porcanal == {"nick": True, "lanny": False}


def test_regenerar_el_link_no_borra_la_fecha_de_publicacion(store):
    """Re-taguear un link o rehacer el video no cambia cuando salio al aire."""
    store.registrar(1, canal="nick", link="viejo")
    store.marcar_publicado(1, "nick", cuando=_HOY)
    store.registrar(1, canal="nick", link="nuevo")
    v = store.listar()[0]
    assert v.link == "nuevo"
    assert v.publicado_ts == _HOY


def test_sin_publicar(store):
    store.registrar(1, canal="nick")
    store.registrar(2, canal="nick")
    store.marcar_publicado(1, "nick")
    assert [v.item_id for v in store.sin_publicar()] == [2]


def test_migracion_de_una_base_sin_la_columna(tmp_path):
    """Una base creada antes de que existiera `publicado_ts` tiene que seguir
    abriendo, con los datos intactos."""
    import sqlite3
    db = tmp_path / "vieja.db"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE videos_producidos ("
        "item_id INTEGER NOT NULL, canal TEXT NOT NULL, ts REAL NOT NULL, "
        "titulo TEXT, link TEXT, precio REAL, comision_pct REAL, "
        "herramienta TEXT, marca TEXT, archivo TEXT, PRIMARY KEY (item_id, canal))"
    )
    con.execute(
        "INSERT INTO videos_producidos (item_id, canal, ts, titulo) VALUES (7,'nick',1.0,'Viejo')"
    )
    con.commit()
    con.close()

    from src.grabados_store import VideosStore as VS
    store = VS(db)
    v = store.listar()[0]
    assert v.titulo == "Viejo"
    assert v.publicado is False
    assert store.marcar_publicado(7, "nick") is True


# --- marcas que vienen del panel ---


def test_marcar_si_falta_marca_uno_sin_publicar(store):
    store.registrar(1, canal="lanny")
    assert store.marcar_si_falta(1, "lanny", cuando=_HOY) is True
    assert store.listar()[0].publicado_ts == _HOY


def test_marcar_si_falta_no_pisa_uno_publicado(store):
    """La fecha mas vieja es la real: una marca del panel no corre una ya puesta."""
    store.registrar(1, canal="lanny")
    store.marcar_publicado(1, "lanny", cuando=_HOY)
    assert store.marcar_si_falta(1, "lanny", cuando=_HOY + 999) is False
    assert store.listar()[0].publicado_ts == _HOY


def test_marcar_si_falta_inexistente(store):
    assert store.marcar_si_falta(999, "lanny", cuando=_HOY) is False


# --- legenda: el texto que se pega en Shopee Video al publicar ---


def test_registrar_guarda_la_legenda(store):
    store.registrar(1, canal="lanny", legenda="Vaso decorativo. #decoracao")
    assert store.listar()[0].legenda == "Vaso decorativo. #decoracao"


def test_registrar_sin_legenda_no_borra_la_que_habia(store):
    """Regenerar un link o rehacer el video no tiene por que perder el texto."""
    store.registrar(1, canal="lanny", legenda="Vaso decorativo. #decoracao")
    store.registrar(1, canal="lanny", link="https://s.shopee.com.br/nuevo")
    assert store.listar()[0].legenda == "Vaso decorativo. #decoracao"


def test_poner_legenda_en_un_video_existente(store):
    store.registrar(1, canal="nick")
    assert store.poner_legenda(1, "nick", "Mouse sem fio. #mouse") is True
    assert store.listar()[0].legenda == "Mouse sem fio. #mouse"


def test_poner_legenda_inexistente(store):
    assert store.poner_legenda(999, "nick", "x") is False


def test_poner_legenda_rechaza_mas_de_150_caracteres(store):
    """Es el limite del campo de Shopee: una legenda mas larga no se puede pegar."""
    store.registrar(1, canal="nick")
    with pytest.raises(ValueError):
        store.poner_legenda(1, "nick", "x" * 151)
    assert store.listar()[0].legenda is None


def test_base_vieja_sin_columna_legenda_se_migra(tmp_path):
    import sqlite3
    ruta = tmp_path / "vieja.db"
    c = sqlite3.connect(ruta)
    c.execute(
        "CREATE TABLE videos_producidos ("
        "item_id INTEGER NOT NULL, canal TEXT NOT NULL, ts REAL NOT NULL, "
        "titulo TEXT, link TEXT, precio REAL, comision_pct REAL, "
        "herramienta TEXT, marca TEXT, archivo TEXT, publicado_ts REAL, "
        "PRIMARY KEY (item_id, canal))")
    c.execute("INSERT INTO videos_producidos (item_id, canal, ts) VALUES (1, 'nick', 1)")
    c.commit()
    c.close()
    store = VideosStore(ruta)
    assert store.listar()[0].legenda is None
    assert store.poner_legenda(1, "nick", "ok") is True
