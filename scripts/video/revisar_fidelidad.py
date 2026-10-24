"""Revisar que un video sea fiel al producto ANTES de publicarlo en Shopee Video.

    python scripts/video/revisar_fidelidad.py                  # lista los pendientes de revisar (canal nick)
    python scripts/video/revisar_fidelidad.py --aprobar 123    # lo viste y es fiel: ya se puede publicar

Por cada video sin aprobar imprime los avisos medibles (poco movimiento, Flow Music)
y deja una hoja de contactos en logs/fidelidad/<item_id>.png para MIRARLA contra la
pagina del producto: ¿es el mismo producto (color, forma, luces, piezas)?, ¿hay
personas u objetos de mas?, ¿el primer cuadro ya es el producto real? Si no es fiel,
no se aprueba: se rehace el video (rehacerlo borra la aprobacion).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BOT))

from src.fidelidad import _ffmpeg, avisos  # noqa: E402
from src.grabados_store import VideosStore  # noqa: E402
from src.publicador_celular import ruta_video  # noqa: E402


def hoja(video: Path, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [_ffmpeg(), "-v", "error", "-y", "-i", str(video), "-vf",
         "fps=1/1.5,scale=180:-1,tile=6x2", "-frames:v", "1", str(destino)],
        check=True,
    )


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--canal", default="nick")
    ap.add_argument("--aprobar", type=int, metavar="ITEM_ID")
    args = ap.parse_args()
    store = VideosStore(BOT / "grabados.db")

    if args.aprobar:
        if not store.aprobar_fidelidad(args.aprobar, args.canal):
            print(f"No existe el video {args.aprobar} del canal {args.canal}.")
            return 1
        print(f"Aprobado {args.aprobar}: ya se puede publicar.")
        return 0

    pendientes = [v for v in store.sin_publicar(args.canal) if not v.fidelidad_ts]
    print(f"{len(pendientes)} video(s) sin revisar ({args.canal}):\n")
    for v in pendientes:
        ruta = ruta_video(v.archivo)
        print(f"- {v.item_id} | {v.titulo[:70]}")
        if not ruta.is_file():
            print("    no existe el archivo\n")
            continue
        for a in avisos(ruta, v.herramienta) or ["sin avisos medibles (igual hay que mirarlo)"]:
            print(f"    ! {a}")
        h = BOT / "logs" / "fidelidad" / f"{v.item_id}.png"
        hoja(ruta, h)
        print(f"    hoja: {h}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
