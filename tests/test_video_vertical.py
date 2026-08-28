"""Videos sintéticos generados con el propio ffmpeg (patrón de barras), para no
versionar material de terceros ni depender de la red."""

import subprocess

import pytest

from src.video_vertical import (
    MODO_MARCO,
    MODO_RECORTE,
    ffmpeg_exe,
    medidas,
    to_vertical,
)


def _video_horizontal(destino, ancho=640, alto=360, segundos=1) -> str:
    ruta = str(destino)
    subprocess.run(
        [ffmpeg_exe(), "-y", "-f", "lavfi",
         "-i", f"testsrc=size={ancho}x{alto}:rate=10:duration={segundos}",
         "-pix_fmt", "yuv420p", ruta],
        capture_output=True, timeout=120, check=True,
    )
    return ruta


@pytest.fixture
def horizontal(tmp_path):
    return _video_horizontal(tmp_path / "entrada.mp4")


def test_convierte_a_9_16(horizontal, tmp_path):
    salida = str(tmp_path / "salida.mp4")
    assert to_vertical(horizontal, salida, ancho=270, alto=480) is True
    assert medidas(salida) == (270, 480)


def test_la_entrada_era_horizontal(horizontal):
    w, h = medidas(horizontal)
    assert w > h


def test_acepta_medidas_por_defecto(horizontal, tmp_path):
    salida = str(tmp_path / "full.mp4")
    assert to_vertical(horizontal, salida) is True
    assert medidas(salida) == (1080, 1920)


def test_entrada_inexistente_devuelve_false(tmp_path):
    salida = str(tmp_path / "nada.mp4")
    assert to_vertical(str(tmp_path / "no-existe.mp4"), salida) is False


def test_medidas_de_archivo_invalido_es_none(tmp_path):
    roto = tmp_path / "roto.mp4"
    roto.write_bytes(b"esto no es un video")
    assert medidas(str(roto)) is None


# --- modo recorte ---

def test_recorte_tambien_da_9_16(horizontal, tmp_path):
    salida = str(tmp_path / "recorte.mp4")
    assert to_vertical(horizontal, salida, ancho=270, alto=480, modo=MODO_RECORTE) is True
    assert medidas(salida) == (270, 480)


def test_los_dos_modos_producen_las_mismas_medidas(horizontal, tmp_path):
    a, b = str(tmp_path / "a.mp4"), str(tmp_path / "b.mp4")
    to_vertical(horizontal, a, ancho=270, alto=480, modo=MODO_MARCO)
    to_vertical(horizontal, b, ancho=270, alto=480, modo=MODO_RECORTE)
    assert medidas(a) == medidas(b) == (270, 480)


def test_modo_desconocido_cae_en_marco(horizontal, tmp_path):
    """Degradacion segura: un modo mal escrito no debe romper la conversion."""
    salida = str(tmp_path / "raro.mp4")
    assert to_vertical(horizontal, salida, ancho=270, alto=480, modo="inventado") is True
    assert medidas(salida) == (270, 480)
