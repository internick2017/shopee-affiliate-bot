"""Convierte a 9:16 el video horizontal que devuelve el generador (Gemini/Veo).

El porqué: el formato de salida de Veo es un parámetro de generación
(`aspect_ratio`, default "16:9"), no algo que se deduzca de la imagen de
referencia ni del prompt. La app de Gemini no expone ese control, así que por
mucho que uno pida vertical, el video sale horizontal. Como el parámetro no está
a mano, el formato se arregla después: el video se reencuadra localmente.

Dos modos, porque hay un compromiso real y depende del video:

  - MARCO: banda central con el video entero + relleno difuminado derivado de si
    mismo. No pierde nada de imagen, pero se nota que el contenido no fue hecho
    para vertical: quedan dos franjas y el ojo las lee como enmarcado.
  - RECORTE: agranda el video hasta llenar el cuadro vertical y corta los
    costados. Se ve nativo, a pantalla completa, sin franjas; a cambio pierde
    aproximadamente dos tercios del ancho y baja la resolucion efectiva.

RECORTE sirve cuando el producto esta centrado en el cuadro, que es lo habitual en
un video de producto: lo que se va son los costados, que son fondo. Si el producto
se mueve o esta descentrado, MARCO es lo seguro. Por eso conviven en vez de que uno
reemplace al otro.

ffmpeg viene del paquete `imageio-ffmpeg`, que trae el binario: en Windows evita
tener que instalarlo aparte y ponerlo en el PATH.
"""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)

_ANCHO = 1080
_ALTO = 1920
# Mismo criterio visual que `vertical_canvas`: fondo muy borroso, desaturado y
# oscurecido, para que no le compita al video del centro.
_DESENFOQUE = 70
_SATURACION = 0.6
_BRILLO = -0.18


def ffmpeg_exe() -> str:
    """Ruta al binario de ffmpeg que trae `imageio-ffmpeg`."""
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


MODO_MARCO = "marco"
MODO_RECORTE = "recorte"


def _filtro_recorte(ancho: int, alto: int) -> str:
    """Agranda hasta CUBRIR el lienzo vertical y recorta al centro. Sin franjas."""
    return (
        f"scale={ancho}:{alto}:force_original_aspect_ratio=increase,"
        f"crop={ancho}:{alto}"
    )


def _filtro(ancho: int, alto: int) -> str:
    """Grafo de filtros: el video se duplica en fondo y frente. El fondo se agranda
    hasta cubrir el lienzo vertical, se recorta y se difumina; el frente se escala
    al ancho completo y se centra encima."""
    return (
        f"[0:v]split=2[bg][fg];"
        f"[bg]scale={ancho}:{alto}:force_original_aspect_ratio=increase,"
        f"crop={ancho}:{alto},"
        f"gblur=sigma={_DESENFOQUE},"
        f"eq=saturation={_SATURACION}:brightness={_BRILLO}[fondo];"
        # -2 = alto automático divisible por 2, requisito de los codecs h264.
        f"[fg]scale={ancho}:-2[frente];"
        f"[fondo][frente]overlay=(W-w)/2:(H-h)/2"
    )


def to_vertical(
    entrada: str,
    salida: str,
    *,
    ancho: int = _ANCHO,
    alto: int = _ALTO,
    modo: str = MODO_MARCO,
    timeout: int = 300,
) -> bool:
    """Reencuadra `entrada` a `ancho` x `alto` y lo escribe en `salida`.

    `modo`: MODO_MARCO (banda + fondo difuminado) o MODO_RECORTE (pantalla
    completa, corta los costados). Ver el docstring del modulo por el compromiso.

    Devuelve True si ffmpeg terminó bien. No lanza: ante fallo loguea y devuelve
    False, para que el llamador pueda degradar a entregar el video original."""
    if modo == MODO_RECORTE:
        filtro = ["-vf", _filtro_recorte(ancho, alto)]
    else:
        filtro = ["-filter_complex", _filtro(ancho, alto)]
    cmd = [
        ffmpeg_exe(),
        "-y",
        "-i", entrada,
        *filtro,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        # El audio se copia tal cual; si no hay, `-c:a copy` no molesta.
        "-c:a", "copy",
        salida,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception:
        logger.warning("No se pudo ejecutar ffmpeg", exc_info=True)
        return False
    if r.returncode != 0:
        logger.warning("ffmpeg falló (código %s): %s", r.returncode, (r.stderr or "")[-400:])
        return False
    return True


def medidas(ruta: str) -> tuple[int, int] | None:
    """(ancho, alto) del video, o None si no se puede leer. Usa ffmpeg, no ffprobe,
    porque `imageio-ffmpeg` solo trae el primero."""
    try:
        r = subprocess.run(
            [ffmpeg_exe(), "-i", ruta], capture_output=True, text=True, timeout=60
        )
        for linea in (r.stderr or "").splitlines():
            if "Video:" in linea:
                for parte in linea.split(","):
                    parte = parte.strip().split(" ")[0]
                    if "x" in parte:
                        w, _, h = parte.partition("x")
                        if w.isdigit() and h.isdigit():
                            return int(w), int(h)
    except Exception:
        logger.warning("No se pudieron leer las medidas del video", exc_info=True)
    return None
