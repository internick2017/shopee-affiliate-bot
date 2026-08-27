"""Imágenes sintéticas (no fotos reales) para no versionar contenido de terceros:
un cuadrado de un color sólido, con o sin la franja verde que imita el watermark
de Promocasinha en la mitad inferior."""

import asyncio
import io

from PIL import Image

from src.image_watermark import strip_watermark, strip_watermark_from_media


def _jpeg_bytes(im) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="JPEG")
    return buf.getvalue()


def _plain_image(size=200, color=(240, 240, 240)) -> bytes:
    return _jpeg_bytes(Image.new("RGB", (size, size), color))


def _watermarked_image(size=200, bg=(240, 240, 240), band_top_frac=0.82) -> bytes:
    """Fondo `bg` con una franja verde (misma dominancia de canal que el watermark
    real) desde `band_top_frac` hasta abajo."""
    im = Image.new("RGB", (size, size), bg)
    band_top = int(size * band_top_frac)
    green_band = Image.new("RGB", (size, size - band_top), (120, 200, 90))
    im.paste(green_band, (0, band_top))
    return _jpeg_bytes(im)


def test_plain_image_is_returned_unchanged():
    original = _plain_image()
    assert strip_watermark(original) == original


def test_watermarked_image_is_cropped_above_the_green_band():
    original = _watermarked_image(size=200, band_top_frac=0.82)
    cleaned = strip_watermark(original)
    assert cleaned != original

    out = Image.open(io.BytesIO(cleaned))
    w, h = out.size
    assert w == 200
    # El recorte cae antes de donde arranca la franja verde (con margen).
    assert h < 200 * 0.82


def test_watermark_survives_over_a_dark_background():
    """El watermark real es semitransparente: sobre fondo oscuro el verde se ve
    más apagado, no el verde claro de un fondo blanco. La detección tiene que
    igual encontrarlo (ver el ajuste de umbral en image_watermark.py)."""
    original = _watermarked_image(size=200, bg=(20, 20, 20), band_top_frac=0.82)
    cleaned = strip_watermark(original)
    assert cleaned != original
    out = Image.open(io.BytesIO(cleaned))
    assert out.size[1] < 200 * 0.82


def test_broken_bytes_are_returned_unchanged():
    garbage = b"no soy una imagen"
    assert strip_watermark(garbage) == garbage


class _FakeClient:
    def __init__(self, payload: bytes | None, *, fail: bool = False):
        self._payload = payload
        self._fail = fail

    async def download_media(self, media, file):
        if self._fail:
            raise RuntimeError("Telegram caído")
        return self._payload


def test_strip_from_media_returns_a_named_buffer_when_watermarked():
    payload = _watermarked_image()
    client = _FakeClient(payload)
    result = asyncio.run(strip_watermark_from_media(client, media="the-photo-ref"))
    assert isinstance(result, io.BytesIO)
    assert result.name == "photo.jpg"
    assert result.getvalue() != payload


def test_strip_from_media_falls_back_to_the_original_media_on_download_failure():
    client = _FakeClient(None, fail=True)
    result = asyncio.run(strip_watermark_from_media(client, media="the-photo-ref"))
    assert result == "the-photo-ref"


def test_strip_from_media_falls_back_when_download_is_empty():
    client = _FakeClient(b"")
    result = asyncio.run(strip_watermark_from_media(client, media="the-photo-ref"))
    assert result == "the-photo-ref"
