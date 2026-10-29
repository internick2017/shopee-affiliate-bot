"""Tapa un defecto localizado de un video crudo en vez de regenerarlo (regla de Nick, 2026-10-29).

Primera opcion, la foto del producto (SIEMPRE la primera imagen del anuncio) justo encima del
defecto; si no entra, una caja de texto. Va ANTES de `aplicar_marca.py`. Coordenadas en pixeles
del video de entrada (720x1280 si viene de Flow).

Uso:
    python scripts/video/tapar_defecto.py foto  entrada.mp4 salida.mp4 foto.jpg X Y ANCHO T0 T1
    python scripts/video/tapar_defecto.py texto entrada.mp4 salida.mp4 "linea1|linea2" Y T0 T1 COLOR

T1 = fin para dejarlo hasta el final. COLOR tipo 0xD81B60 (identidad de Lanny) o 0x0D0D0D.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
FUENTE = r"C\:/Windows/Fonts/segoeuib.ttf"


def ventana(t0: str, t1: str) -> str:
    return f"gte(t,{t0})" if t1 == "fin" else f"between(t,{t0},{t1})"


def main() -> int:
    modo, ent, sal = sys.argv[1:4]
    if modo == "foto":
        foto, x, y, ancho, t0, t1 = sys.argv[4:10]
        filtro = (f"[1:v]scale={ancho}:-1,pad=iw+12:ih+12:6:6:white[ph];"
                  f"[0:v][ph]overlay={x}:{y}:enable='{ventana(t0, t1)}'")
        cmd = [FF, "-y", "-loglevel", "error", "-i", ent, "-i", foto, "-filter_complex", filtro]
    else:
        lineas, y, t0, t1, color = sys.argv[4:9]
        texto = Path(tempfile.gettempdir()) / "tapar_defecto.txt"
        # newline: con \r\n (el default en Windows) ffmpeg duplica el interlineado.
        texto.write_text(lineas.replace("|", "\n"), encoding="utf-8", newline="\n")
        ruta = str(texto).replace("\\", "/").replace(":", r"\:")
        # Alineada a la derecha: arriba a la izquierda va la foto de `aplicar_marca --foto`
        # (2026-10-29: tapaba el comienzo de la segunda linea del smartwatch).
        filtro = (f"drawtext=fontfile='{FUENTE}':textfile='{ruta}':fontsize=48:fontcolor=white:"
                  f"line_spacing=10:box=1:boxcolor={color}@0.95:boxborderw=30:x=w-text_w-46:y={y}:"
                  f"enable='{ventana(t0, t1)}'")
        cmd = [FF, "-y", "-loglevel", "error", "-i", ent, "-vf", filtro]
    cmd += ["-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "copy", sal]
    subprocess.run(cmd, check=True)
    print("OK", sal)
    return 0


if __name__ == "__main__":
    sys.exit(main())
