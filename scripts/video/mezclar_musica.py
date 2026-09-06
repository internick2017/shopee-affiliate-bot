"""Mete una pista de musica de fondo debajo de la narracion de un video.

Pensado para el paso final del flujo: el video de Google Flow ya trae narracion en
portugues, y la musica de Google Flow Music va **debajo**, no encima. Por eso el
volumen por defecto es bajo (18%): si sube mas, tapa la voz.

El video **no se recomprime**: se copia el stream de video tal cual y solo se
rehace el audio. Asi la marca de agua ya estampada no pierde calidad.

La pista suele durar minutos y el video segundos, asi que se recorta a la duracion
del video y se le pone un fade out al final para que no corte de golpe.

Uso:
    python mezclar_musica.py video.mp4 musica.mp3 salida.mp4
    python mezclar_musica.py video.mp4 musica.mp3 salida.mp4 --volumen 0.12
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

VOLUMEN = 0.18       # la voz manda; la musica acompana
FADE_SEGUNDOS = 1.5  # cola para que no termine de golpe


def ffmpeg_exe() -> str:
    """El binario que trae `imageio-ffmpeg`, igual que el bot: en Windows evita
    tener que instalar ffmpeg aparte y ponerlo en el PATH."""
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def duracion(ruta: Path) -> float | None:
    """Segundos de un archivo, leidos de la salida de ffmpeg. None si no se puede."""
    res = subprocess.run([ffmpeg_exe(), "-i", str(ruta)], capture_output=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", res.stderr.decode(errors="replace"))
    if not m:
        return None
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def tiene_audio(ruta: Path) -> bool:
    res = subprocess.run([ffmpeg_exe(), "-i", str(ruta)], capture_output=True)
    return "Audio:" in res.stderr.decode(errors="replace")


def mezclar(video: Path, musica: Path, salida: Path, volumen: float = VOLUMEN) -> bool:
    """Pone `musica` de fondo en `video` y escribe `salida`. No lanza: ante fallo
    imprime el error y devuelve False."""
    for f in (video, musica):
        if not f.is_file():
            print(f"No existe: {f}", file=sys.stderr)
            return False

    dur = duracion(video)
    if dur is None:
        print("No se pudo leer la duracion del video", file=sys.stderr)
        return False

    fade_desde = max(0.0, dur - FADE_SEGUNDOS)
    pista = (
        f"[1:a]atrim=0:{dur},asetpts=N/SR/TB,volume={volumen},"
        f"afade=t=out:st={fade_desde}:d={FADE_SEGUNDOS}[m]"
    )

    if tiene_audio(video):
        # normalize=0 es clave: sin eso amix baja a la mitad el volumen de la voz.
        filtro = f"{pista};[0:a][m]amix=inputs=2:duration=first:normalize=0[a]"
    else:
        # Video mudo: la musica pasa a ser el audio principal, a volumen pleno.
        filtro = (
            f"[1:a]atrim=0:{dur},asetpts=N/SR/TB,"
            f"afade=t=out:st={fade_desde}:d={FADE_SEGUNDOS}[a]"
        )
        print("El video no trae audio: la musica va a volumen completo.")

    cmd = [
        ffmpeg_exe(), "-y",
        "-i", str(video),
        "-i", str(musica),
        "-filter_complex", filtro,
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy",          # el video no se toca
        "-c:a", "aac", "-b:a", "160k",
        str(salida),
    ]
    res = subprocess.run(cmd, capture_output=True, timeout=300)
    if res.returncode != 0:
        print(res.stderr.decode(errors="replace")[-2000:], file=sys.stderr)
        return False
    return True


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("video", type=Path)
    p.add_argument("musica", type=Path)
    p.add_argument("salida", type=Path)
    p.add_argument("--volumen", type=float, default=VOLUMEN,
                   help=f"0 a 1. Por defecto {VOLUMEN}, que deja la voz adelante")
    args = p.parse_args()

    ok = mezclar(args.video, args.musica, args.salida, args.volumen)
    if ok:
        print(f"Listo: {args.salida}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
