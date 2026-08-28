"""Imágenes sintéticas (no fotos reales) para no versionar contenido de terceros.
Las aserciones son geométricas: proporción, zona segura y producto completo."""

import io

from PIL import Image

from src.vertical_canvas import (
    _ANCHO_MAX_PRODUCTO,
    _MARGEN_INFERIOR,
    _MARGEN_SUPERIOR,
    _medidas_producto,
    build_vertical_canvas,
)


def _jpeg_bytes(im) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="JPEG")
    return buf.getvalue()


def _cuadrada(size=800, color=(200, 120, 60)) -> bytes:
    return _jpeg_bytes(Image.new("RGB", (size, size), color))


def _abrir(raw: bytes):
    return Image.open(io.BytesIO(raw))


def test_salida_es_1080x1920():
    assert _abrir(build_vertical_canvas(_cuadrada())).size == (1080, 1920)


def test_proporcion_es_9_16():
    w, h = _abrir(build_vertical_canvas(_cuadrada())).size
    assert round(w / h, 4) == round(9 / 16, 4)


def test_acepta_dimensiones_a_medida():
    assert _abrir(build_vertical_canvas(_cuadrada(), ancho=540, alto=960)).size == (540, 960)


def test_producto_entra_completo_sin_recortar():
    """Contain, no cover: la escala la manda el lado más restrictivo."""
    nw, nh, _x, _y = _medidas_producto(800, 800, 1080, 1920)
    alto_disp = 1920 * (1 - _MARGEN_SUPERIOR - _MARGEN_INFERIOR)
    assert nw <= 1080 * _ANCHO_MAX_PRODUCTO + 1
    assert nh <= alto_disp + 1
    assert round(nw / nh, 3) == 1.0  # conserva la proporción original


def test_producto_dentro_de_la_zona_segura():
    _nw, nh, _x, y = _medidas_producto(800, 800, 1080, 1920)
    assert y >= 1920 * _MARGEN_SUPERIOR - 1
    assert y + nh <= 1920 * (1 - _MARGEN_INFERIOR) + 1


def test_producto_centrado_horizontalmente():
    nw, _nh, x, _y = _medidas_producto(800, 800, 1080, 1920)
    assert abs(x - (1080 - nw) / 2) <= 1


def test_imagen_horizontal_tambien_entra_completa():
    nw, nh, x, y = _medidas_producto(1600, 900, 1080, 1920)
    assert nw <= 1080 * _ANCHO_MAX_PRODUCTO + 1
    assert x >= 0 and y >= 0
    assert round(nw / nh, 2) == round(1600 / 900, 2)


def test_sin_barras_negras_en_los_extremos():
    """El relleno sale de la foto, así que las esquinas no son negras."""
    im = _abrir(build_vertical_canvas(_cuadrada(color=(200, 120, 60)))).convert("RGB")
    for punto in ((5, 5), (1074, 5), (5, 1914), (1074, 1914)):
        assert sum(im.getpixel(punto)) > 30


def test_bytes_corruptos_devuelven_el_original():
    basura = b"esto no es una imagen"
    assert build_vertical_canvas(basura) == basura
