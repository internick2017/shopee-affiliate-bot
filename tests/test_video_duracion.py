"""El chequeo de imagen contra audio (caso real: espuma Zip Clean, 2026-10-29)."""

from src.video_duracion import problema


def test_imagen_mas_corta_que_el_audio_es_un_problema():
    assert "4.8" in problema(4.83, 8.60)


def test_diferencia_chica_o_sin_audio_esta_bien():
    assert problema(8.5, 8.6) is None
    assert problema(8.5, None) is None


def test_sin_imagen_es_un_problema():
    assert problema(None, 8.0)
