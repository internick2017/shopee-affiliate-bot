"""Frena los videos cuya imagen termina antes que el audio.

Por que (2026-10-29): 5 videos de YouTube Create llegaron con la imagen cortada a
los ~4-5 s y el audio hasta los ~8-10 s. El reproductor deja quieto el ultimo
cuadro y la voz sigue: Lanny lo vio como "la imagen se traba". El problema ya
viene en la descarga de YouTube Create (los crudos lo tienen), y `freezedetect`
no lo ve porque no hay cuadros repetidos: no hay cuadros.

Se mide con el ffmpeg de `imageio-ffmpeg` copiando cada stream sin re-encodear.

Uso, para revisar archivos antes de entregarlos o publicarlos:
    python -m src.video_duracion video1.mp4 video2.mp4 ...
"""

from __future__ import annotations

import re
import subprocess
import sys

TOLERANCIA_S = 0.5


def _ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def duracion_stream(ruta: str, stream: str) -> float | None:
    """Segundos del stream ("v" o "a"), o None si no tiene ese stream."""
    salida = subprocess.run(
        [_ffmpeg(), "-hide_banner", "-i", ruta, "-map", f"0:{stream}?", "-c", "copy",
         "-f", "null", "-"],
        capture_output=True, text=True, errors="replace",
    ).stderr
    tiempos = re.findall(r"time=(\d+):(\d+):([\d.]+)", salida)
    if not tiempos:
        return None
    h, m, s = tiempos[-1]
    return int(h) * 3600 + int(m) * 60 + float(s) or None


def problema(imagen: float | None, audio: float | None) -> str | None:
    """El motivo para no publicar, o None si esta bien. Sin audio no hay problema."""
    if imagen is None:
        return "el archivo no tiene imagen"
    if audio is not None and audio - imagen > TOLERANCIA_S:
        return f"la imagen termina a los {imagen:.1f} s y el audio sigue hasta {audio:.1f} s"
    return None


def problema_del_archivo(ruta: str) -> str | None:
    return problema(duracion_stream(ruta, "v"), duracion_stream(ruta, "a"))


if __name__ == "__main__":
    malos = 0
    for ruta in sys.argv[1:]:
        motivo = problema_del_archivo(ruta)
        malos += bool(motivo)
        print(f"{'MAL' if motivo else 'ok '}  {ruta}" + (f"  ({motivo})" if motivo else ""))
    raise SystemExit(1 if malos else 0)
