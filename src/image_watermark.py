"""Recorta el watermark que Promocasinha pega en algunas de sus fotos: un círculo
verde con el ícono "CS" + "@PROMOCASINHA" abajo de la imagen. Verificado sobre 15
fotos reales (2026-08-01): aparece en ~mitad de las fotos de producto (las que
Promocasinha parece fotografiar/editar ella misma), nunca en las otras 3 fuentes.

El bot reenvía las fotos por referencia de Telegram (ver `posting.py`), así que sin
esto el watermark llega intacto al canal de revisión de Nick — publicidad gratis a
un canal de Telegram competidor.

Detección por color en vez de un recorte fijo: el watermark es semitransparente,
así que su color se mezcla con lo que tenga atrás (blanco, madera, mármol, un
cooktop negro) — un recorte fijo del X% inferior de la imagen cortaría producto de
más en las fotos SIN watermark. En cambio, se busca la dominancia de verde
característica del círculo (canal G bien por encima de R y B) en la mitad inferior
de la imagen, y se recorta justo por encima de la fila más alta donde aparece. Sin
esa dominancia, no se toca la imagen.
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)

_SAMPLE_STEP = 4
_MIN_MATCHES = 120
_MARGIN_PX = 15
_SEARCH_FROM_FRACTION = 0.6


def _find_watermark_top(im) -> int | None:
    """Fila (en píxeles) justo arriba del watermark, o None si no lo encuentra."""
    im = im.convert("RGB")
    w, h = im.size
    y_start = int(h * _SEARCH_FROM_FRACTION)
    px = im.load()
    matches_by_row: dict[int, int] = {}
    for y in range(y_start, h, _SAMPLE_STEP):
        count = 0
        for x in range(0, w, _SAMPLE_STEP):
            r, g, b = px[x, y]
            if g > r + 18 and g > b + 28 and g > 60:
                count += 1
        if count:
            matches_by_row[y] = count
    if sum(matches_by_row.values()) < _MIN_MATCHES:
        return None
    return max(0, min(matches_by_row) - _MARGIN_PX)


def strip_watermark(image_bytes: bytes) -> bytes:
    """Recorta la franja del watermark si lo detecta. Si no lo encuentra, o si
    falla el procesamiento (imagen corrupta, formato raro), devuelve los bytes
    originales sin tocar — nunca vale la pena bloquear el posteo por esto."""
    try:
        from PIL import Image

        im = Image.open(io.BytesIO(image_bytes))
        top = _find_watermark_top(im)
        if top is None:
            return image_bytes
        w, _h = im.size
        cropped = im.convert("RGB").crop((0, 0, w, top))
        out = io.BytesIO()
        cropped.save(out, format="JPEG", quality=92)
        return out.getvalue()
    except Exception:
        logger.warning("No se pudo procesar la imagen para sacar el watermark", exc_info=True)
        return image_bytes


async def strip_watermark_from_media(client, media):
    """Descarga `media` (la foto de Telethon del mensaje original), le saca el
    watermark si lo tiene, y devuelve un file-like listo para `send_file`.

    Ante cualquier fallo (red, descarga, procesamiento) devuelve `media` tal cual
    — se reenvía por referencia como antes de este feature, degradación segura."""
    try:
        raw = await client.download_media(media, file=bytes)
        if not raw:
            return media
        cleaned = strip_watermark(raw)
        buf = io.BytesIO(cleaned)
        buf.name = "photo.jpg"
        return buf
    except Exception:
        logger.warning("No se pudo descargar la foto para sacar el watermark", exc_info=True)
        return media
