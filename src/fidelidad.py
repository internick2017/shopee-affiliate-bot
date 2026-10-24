"""Chequeo previo de un video antes de publicarlo en Shopee Video.

Shopee quita los videos que muestran un producto distinto al vinculado (visto el
2026-10-24: un mouse liso para un anuncio "RGB", un kit con persona y extras). Y un
video casi inmovil, "una foto pegada", rinde poco. Esto mide, sin mirar el contenido:

  - movimiento: cuanto cambia la imagen entre cuadros. Casi cero = foto quieta.
  - herramienta: Flow Music suele deformar el producto.

Lo que NO mide es si el producto es el correcto: eso lo decide una persona mirando
la hoja de contactos (`scripts/video/revisar_fidelidad.py`) y aprobandolo. Un
"salto inicial" (primer cuadro distinto) se probo y no discrimina: los videos buenos
con un corte lo tienen igual.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

ANCHO, ALTO = 64, 112  # alcanza para medir cambio; mas grande solo cuesta tiempo
FPS = 2

# Medido el 2026-10-24 en 60 videos entregados (rango 0.3 a 23): los 5 por debajo de
# 2.0 son los casi quietos (cadeiras 0.32 = foto fija; localizador 1.62 = deriva leve).
MOV_MINIMO = 2.0


def _ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def cuadros(video: Path, fps: int = FPS) -> np.ndarray:
    """Cuadros en gris reducidos: array (n, ALTO, ANCHO) de floats."""
    sal = subprocess.run(
        [_ffmpeg(), "-v", "error", "-i", str(video), "-vf", f"fps={fps},scale={ANCHO}:{ALTO}",
         "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True, check=True,
    ).stdout
    n = len(sal) // (ANCHO * ALTO)
    return np.frombuffer(sal[: n * ANCHO * ALTO], np.uint8).reshape(n, ALTO, ANCHO).astype(float)


def movimiento(c: np.ndarray) -> float:
    """Cambio medio (0 a 255) entre cuadros consecutivos."""
    if len(c) < 2:
        return 0.0
    return float(np.abs(np.diff(c, axis=0)).mean())


def avisos(video: Path, herramienta: str = "") -> list[str]:
    """Motivos para NO publicar sin mirarlo. Lista vacia = nada raro que se mida."""
    c = cuadros(video)
    out = []
    mov = movimiento(c)
    if mov < MOV_MINIMO:
        out.append(f"casi sin movimiento ({mov:.2f}): parece una foto pegada")
    if "music" in herramienta.lower():
        out.append("hecho con Flow Music: suele cambiar la forma o el estilo del producto")
    return out
