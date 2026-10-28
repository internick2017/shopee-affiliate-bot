"""Cruce por TIPO de producto antes de producir videos (solo lectura).

    python scripts/video/repetidos.py lanny "Titulo 1" "Titulo 2" ...
    python scripts/video/repetidos.py nick --dias 7 "Titulo"

Mira `videos_producidos` de esa cuenta y, para lanny, tambien el registro de
TikTok @oh_doce_lar (mismos videos de Lanny). Sale con codigo 1 si algun candidato
repite un tipo de los ultimos DIAS (por defecto 7) o de su mismo lote.
"""

import argparse
import csv
import io
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from src.familias import cruzar  # noqa: E402

TZ = ZoneInfo("America/Sao_Paulo")
REGISTRO_TIKTOK = RAIZ.parent / "tiktok-hogar" / "registro.csv"


def historial(canal: str) -> list[tuple[float, str, str]]:
    con = sqlite3.connect(f"file:{RAIZ / 'grabados.db'}?mode=ro", uri=True)
    filas = [(ts, t or "", f"video {canal}") for ts, t in con.execute(
        "SELECT ts, titulo FROM videos_producidos WHERE canal = ?", (canal,))]
    if canal == "lanny" and REGISTRO_TIKTOK.exists():
        with open(REGISTRO_TIKTOK, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                try:
                    ts = datetime.strptime(r["fecha"], "%Y-%m-%d %H:%M").replace(tzinfo=TZ).timestamp()
                except (KeyError, ValueError):
                    continue
                filas.append((ts, f"{r.get('gancho', '')} {r.get('descripcion', '')}", "TikTok"))
    return filas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("canal", choices=["lanny", "nick"])
    ap.add_argument("titulos", nargs="+")
    ap.add_argument("--dias", type=int, default=7)
    args = ap.parse_args()
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    hay = False
    for titulo, choques in cruzar(args.titulos, historial(args.canal), time.time(), args.dias):
        if choques:
            hay = True
            print(f"REPETIDO  {titulo[:70]}")
            for c in choques:
                print(f"    ya hay -> {c}")
        else:
            print(f"ok        {titulo[:70]}")
    return 1 if hay else 0


if __name__ == "__main__":
    raise SystemExit(main())
