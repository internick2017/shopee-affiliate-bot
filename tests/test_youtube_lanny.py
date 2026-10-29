"""El flujo de subir un video de Lanny a YouTube, sin red."""

import pytest

from src.canal_youtube import CATEGORIA_ESTILO
from src.grabados_store import PublicacionesStore, VideoProducido
from src.youtube_lanny import (
    NoSePublico,
    descripcion,
    pendientes,
    publicar,
    resolver_archivo,
    titulo,
)


def video(archivo="", legenda="Espuma que limpa sofa a seco. Facil demais! #limpeza #sofa"):
    return VideoProducido(item_id=58, canal="lanny", titulo="Espuma Spray Zip Clean 300ml",
                          link="https://s.shopee.com.br/DE-SHOPEE-VIDEO", precio=14.99,
                          comision_pct=8.0, herramienta="Flow", marca="Lanny Herrera",
                          archivo=archivo, ts=1.0, legenda=legenda)


@pytest.fixture
def store(tmp_path):
    return PublicacionesStore(tmp_path / "g.db")


@pytest.fixture
def mp4(tmp_path):
    p = tmp_path / "espuma_lanny.mp4"
    p.write_bytes(b"x")
    return str(p)


def test_titulo_es_la_primera_frase_sin_hashtags():
    assert titulo(video()) == "Espuma que limpa sofa a seco #Shorts"


def test_sin_legenda_usa_el_titulo_de_shopee_y_no_pasa_de_100():
    t = titulo(video(legenda=None))
    assert t == "Espuma Spray Zip Clean 300ml #Shorts"
    assert len(titulo(video(legenda="a" * 300))) <= 100


def test_descripcion_lleva_el_link_nuevo_y_el_aviso():
    d = descripcion(video(), "https://s.shopee.com.br/YT")
    assert "Para comprar, clique aqui: https://s.shopee.com.br/YT" in d
    assert "DE-SHOPEE-VIDEO" not in d
    assert "links de afiliado" in d


def test_publicar_sube_guarda_y_comenta(store, mp4):
    llamadas = {}

    def subir(ruta, tit, desc, token, *, privado, categoria):
        llamadas["subir"] = (ruta, token, privado, categoria)
        return "VID1"

    def comentar(vid, texto, token):
        llamadas["comentar"] = (vid, texto)
        return True

    r = publicar(video(mp4), store, generar_link=lambda item: f"https://s.shopee.com.br/YT{item}",
                 access_token=lambda: "tok", subir=subir, comentar=comentar, privado=True,
                 revisar=lambda _: None)

    assert (r.video_id, r.link, r.comentado) == ("VID1", "https://s.shopee.com.br/YT58", True)
    assert llamadas["subir"] == (mp4, "tok", True, CATEGORIA_ESTILO)
    assert llamadas["comentar"] == ("VID1", "Link do produto: https://s.shopee.com.br/YT58")
    assert store.id_externo(58, "lanny", "youtube") == "VID1"
    assert store.ids_publicados("lanny", "youtube") == {58}
    assert store.link_publicado(58, "lanny", "youtube") == "https://s.shopee.com.br/YT58"


def test_no_sube_dos_veces(store, mp4):
    store.registrar(58, canal="lanny", plataforma="youtube", id_externo="VIEJO")
    with pytest.raises(NoSePublico, match="VIEJO"):
        publicar(video(mp4), store, generar_link=lambda _: "x", access_token=lambda: "t",
                 subir=lambda *a, **k: pytest.fail("no deberia subir"), comentar=lambda *a: True)


def test_si_la_subida_falla_no_guarda_nada(store, mp4):
    with pytest.raises(NoSePublico, match="fallo"):
        publicar(video(mp4), store, generar_link=lambda _: "x", access_token=lambda: "t",
                 subir=lambda *a, **k: None, comentar=lambda *a: True, revisar=lambda _: None)
    assert store.ids_publicados("lanny", "youtube") == set()


def test_sin_archivo_no_pide_link_ni_sube(store):
    with pytest.raises(NoSePublico, match="archivo"):
        publicar(video("no/existe.mp4"), store, generar_link=lambda _: pytest.fail("no"),
                 access_token=lambda: "t", subir=lambda *a, **k: "X", comentar=lambda *a: True)


def test_pendientes_saca_los_subidos_y_los_sin_archivo(mp4):
    a, b, c = video(mp4), video(mp4), video("no/existe.mp4")
    b.item_id, c.item_id = 59, 60
    assert [v.item_id for v in pendientes([a, b, c], publicados={58})] == [59]


def test_credencial_se_guarda_y_se_lee(store):
    assert store.credencial("youtube_lanny_refresh") is None
    store.guardar_credencial("youtube_lanny_refresh", "r1")
    store.guardar_credencial("youtube_lanny_refresh", "r2")
    assert store.credencial("youtube_lanny_refresh") == "r2"


def test_archivo_guardado_sin_carpeta_se_busca_en_entregados(tmp_path, mp4):
    assert resolver_archivo(video("espuma_lanny.mp4"), tmp_path).archivo == mp4
    assert resolver_archivo(video("otro.mp4"), tmp_path).archivo == "otro.mp4"


def test_video_con_imagen_cortada_no_se_sube(store, mp4):
    with pytest.raises(NoSePublico, match="rehacerlo"):
        publicar(video(mp4), store, generar_link=lambda _: pytest.fail("no"),
                 access_token=lambda: "t", subir=lambda *a, **k: pytest.fail("no"),
                 comentar=lambda *a: True, revisar=lambda _: "la imagen termina antes")
