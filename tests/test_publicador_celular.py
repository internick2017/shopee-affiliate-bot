"""La parte del publicador que decide, sin celular: que video sigue y si el
producto que muestra la app es el registrado."""

from src.grabados_store import VideosStore
from src.publicador_celular import (
    bloqueado,
    elegir_producto,
    es_verde,
    normalizar,
    publicados_hoy,
    ruta_video,
    siguiente_video,
)


def test_es_verde_distingue_prendido_de_apagado():
    assert es_verde(9, 198, 46)  # pista de un interruptor prendido (medido)
    assert not es_verde(252, 252, 252)  # bolita blanca de uno apagado (medido)
    assert not es_verde(225, 225, 225)  # pista gris
    assert not es_verde(240, 80, 40)  # el naranja de Shopee

# Titulos reales de la app al buscar "cadeado biometrico digital" el 2026-10-15.
RESULTADOS = [
    "Cadeado Biométrico Inteligente Sem Chave, Abertura Digital Cinza",
    "Cadeado Biométrico Inteligente Sem Chave, Abertura Digital PRETO",
    "NAIERDI Smart lock – Fechadura Biométrica De Impressão Digital Sem Chave",
]


def test_normalizar_saca_acentos_y_signos():
    assert normalizar("Cadeado Biométrico, Sem Chave!") == "cadeado biometrico sem chave"


def test_elige_el_que_coincide_y_no_el_parecido():
    assert elegir_producto("Cadeado Biometrico Inteligente Sem Chave Abertura Digital PRETO", RESULTADOS) == 1


def test_acepta_titulo_cortado_de_cualquiera_de_los_dos_lados():
    assert elegir_producto("Cadeado Biométrico Inteligente Sem Chave, Abertura Digital Cinza 2026", RESULTADOS) == 0
    assert elegir_producto("NAIERDI Smart lock – Fechadura", RESULTADOS) == 2


def test_un_texto_corto_de_pantalla_no_cuenta_como_el_producto():
    # "Postar" o "Cadeado" sueltos en la pantalla no prueban nada.
    assert elegir_producto("Cadeado de Impressão Digital", ["Cadeado", "Postar"]) is None


def test_sin_coincidencia_no_elige_nada():
    assert elegir_producto("Ring Light 10 polegadas", RESULTADOS) is None
    assert elegir_producto("", RESULTADOS) is None


def test_ruta_video_relativa_y_absoluta(tmp_path):
    assert ruta_video("a.mp4", tmp_path) == tmp_path / "a.mp4"
    absoluta = tmp_path / "otra" / "b.mp4"
    assert ruta_video(str(absoluta), tmp_path) == absoluta


def test_siguiente_video_saltea_los_incompletos(tmp_path):
    store = VideosStore(tmp_path / "g.db")
    (tmp_path / "listo.mp4").write_bytes(b"x")
    store.registrar(1, canal="nick", titulo="Sin legenda", link="l", archivo="listo.mp4", now=500)
    store.registrar(2, canal="nick", titulo="Sin archivo", link="l", archivo="no.mp4", legenda="x", now=400)
    store.registrar(3, canal="nick", titulo="Sin link", archivo="listo.mp4", legenda="x", now=300)
    store.registrar(4, canal="nick", titulo="Listo", link="l", archivo="listo.mp4", legenda="hola", now=100)
    store.registrar(5, canal="lanny", titulo="Otro canal", link="l", archivo="listo.mp4", legenda="x", now=600)
    v = siguiente_video(store, "nick", tmp_path)
    assert v is not None and v.item_id == 4


def test_siguiente_video_no_repite_lo_publicado(tmp_path):
    store = VideosStore(tmp_path / "g.db")
    (tmp_path / "a.mp4").write_bytes(b"x")
    store.registrar(1, canal="nick", titulo="A", link="l", archivo="a.mp4", legenda="x")
    store.marcar_publicado(1, "nick")
    assert siguiente_video(store, "nick", tmp_path) is None


def test_bloqueado_lee_el_dumpsys_del_a07():
    # Lineas reales de `dumpsys window` del Galaxy A07 (2026-10-15).
    assert not bloqueado("mShowingDream=false mDreamingLockscreen=false\nisKeyguardShowing=false")
    assert bloqueado("isKeyguardShowing=true")


def test_publicados_hoy_cuenta_desde_la_medianoche_local(tmp_path):
    import time

    store = VideosStore(tmp_path / "g.db")
    ahora = time.mktime((2026, 10, 15, 14, 0, 0, 0, 0, -1))
    for i, hora in enumerate((1, 9, 13)):  # tres de hoy
        store.registrar(i, canal="nick", titulo="x")
        store.marcar_publicado(i, "nick", cuando=time.mktime((2026, 10, 15, hora, 0, 0, 0, 0, -1)))
    store.registrar(9, canal="nick", titulo="ayer")
    store.marcar_publicado(9, "nick", cuando=time.mktime((2026, 10, 14, 23, 0, 0, 0, 0, -1)))
    store.registrar(10, canal="nick", titulo="sin publicar")
    store.registrar(11, canal="lanny", titulo="otro canal")
    store.marcar_publicado(11, "lanny", cuando=ahora)
    assert publicados_hoy(store, "nick", ahora=ahora) == 3
