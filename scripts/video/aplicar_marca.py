"""Pega la marca de agua sobre un video que YA viene vertical (9:16).

Por que existe aparte de `video_vertical.to_vertical()` del bot: esa funcion hace
dos cosas juntas, reencuadrar a 9:16 y pegar la marca. Los videos de Google Flow
ya salen verticales, asi que reencuadrarlos es trabajo de mas, y en MODO_MARCO
hasta les agregaria franjas. Aca se pega la marca y nada mas.

Los parametros visuales (ancho, opacidad, margen, esquina) son los mismos que usa
el bot en `src/video_vertical.py`, para que un video de Flow y uno del bot se vean
iguales.

**De quien es la marca hay que elegirlo siempre**, no hay default: Nick publica en
tres canales, el de Lanny, el propio y el de Setup Justo, y estampar el equivocado
obliga a rehacer el video. Si no se dice cual, el script falla y lo pide.

Uso:
    python aplicar_marca.py entrada.mp4 salida.mp4 --para nick
    python aplicar_marca.py entrada.mp4 salida.mp4 --para lanny
    python aplicar_marca.py entrada.mp4 salida.mp4 --para setupjusto
    python aplicar_marca.py entrada.mp4 salida.mp4 --marca C:/ruta/otra.png
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Mismos valores que `src/video_vertical.py` del bot.
ANCHO_MARCA = 220
OPACIDAD = 0.75
MARGEN = 28

# Vive en scripts/video/ del repo del bot: la raiz esta dos niveles arriba.
# Calcularla asi y no con una ruta absoluta permite mover o clonar el repo
# sin editar el script.
_ASSETS = Path(__file__).resolve().parents[2] / "assets"
MARCAS = {
    "lanny": _ASSETS / "watermark.png",       # @lannyherrera, la que usa el bot
    "nick": _ASSETS / "watermark-nick.png",   # @nickgranados, canal propio
    # Setup Justo lleva el DOMINIO y no un usuario de Shopee, a diferencia de las
    # otras dos: sus videos van a YouTube, donde el reproductor ya muestra el
    # handle del canal debajo, y lo que hay que empujar es el sitio, que es donde
    # viven el historial de precios y los enlaces de afiliado.
    "setupjusto": _ASSETS / "watermark-setupjusto.png",   # setupjusto.com.br
}


def ffmpeg_exe() -> str:
    """El binario que trae `imageio-ffmpeg`, igual que el bot: en Windows evita
    tener que instalar ffmpeg aparte y ponerlo en el PATH."""
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def aplicar(entrada: Path, salida: Path, marca: Path, timeout: int = 300) -> bool:
    """Pega `marca` en la esquina inferior derecha de `entrada` y escribe `salida`.

    Devuelve True si ffmpeg termino bien. No lanza: ante fallo imprime el error y
    devuelve False, para que el llamador pueda entregar el video sin marca en vez
    de quedarse sin nada."""
    if not entrada.is_file():
        print(f"No existe el video de entrada: {entrada}", file=sys.stderr)
        return False
    if not marca.is_file():
        print(f"No existe la marca de agua: {marca}", file=sys.stderr)
        return False

    filtro = (
        f"[1:v]scale={ANCHO_MARCA}:-1,format=rgba,"
        f"colorchannelmixer=aa={OPACIDAD}[wm];"
        f"[0:v][wm]overlay=W-w-{MARGEN}:H-h-{MARGEN}"
    )
    cmd = [
        ffmpeg_exe(),
        "-y",
        "-i",
        str(entrada),
        "-i",
        str(marca),
        "-filter_complex",
        filtro,
        "-c:a",
        "copy",  # el audio (la narracion) pasa intacto, sin recomprimir
        str(salida),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print("ffmpeg tardo demasiado", file=sys.stderr)
        return False
    if res.returncode != 0:
        print(res.stderr.decode(errors="replace")[-2000:], file=sys.stderr)
        return False
    return True


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("entrada", type=Path)
    p.add_argument("salida", type=Path)
    grupo = p.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--para", choices=sorted(MARCAS), help="de quien es el canal")
    grupo.add_argument("--marca", type=Path, help="ruta a un PNG de marca propio")
    args = p.parse_args()

    marca = args.marca if args.marca else MARCAS[args.para]
    ok = aplicar(args.entrada, args.salida, marca)
    if ok:
        print(f"Listo: {args.salida}  (marca: {marca.name})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
