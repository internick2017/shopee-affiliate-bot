"""Videos sintéticos generados con el propio ffmpeg (patrón de barras), para no
versionar material de terceros ni depender de la red."""

import subprocess

import pytest

from src.video_vertical import ffmpeg_exe, medidas, to_vertical


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
