"""Regenera los links de afiliado de un canal con las credenciales de ESA cuenta.

Existe por un error real, del 2026-09-05: los videos del canal de Nick se hicieron
con links resueltos con las credenciales del `.env` del bot, que son las de la
cuenta de Lanny. El video estaba bien, pero una compra hecha desde el hubiera
comisionado a la otra cuenta.

El video no hay que rehacerlo: lo unico que cambia es el link que se pega en la
publicacion. Este script sigue el redirect del link viejo hasta la URL real del
producto y pide un shortlink nuevo con las credenciales del canal correcto
(`generateShortLink`, la misma mutation que usa `retag_shopee_url` del bot).

Uso:
    python regenerar_links.py --canal nick --dry-run    # ver que haria
    python regenerar_links.py --canal nick              # y guardar en la base
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path

import requests

# Este script vive en scripts/video/ del propio repo del bot.
BOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BOT))

from dotenv import load_dotenv  # noqa: E402

from src.grabados_store import VideosStore  # noqa: E402
from src.shopee_resolver import _USER_AGENT, retag_shopee_url  # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
DB = BOT / "grabados.db"

# Por canal, de donde salen las credenciales de SU cuenta de afiliado.
CUENTAS = {
    "lanny": ("SHOPEE_APP_ID", "SHOPEE_SECRET"),
    "nick": ("SHOPEE_APP_ID_NICK", "SHOPEE_SECRET_NICK"),
}


def url_real(shortlink: str) -> str | None:
    """El shortlink de tracking no sirve para re-taguear: hay que llegar a la URL
    del producto siguiendo el redirect."""
    try:
        r = requests.get(shortlink, headers={"User-Agent": _USER_AGENT},
                         timeout=20, allow_redirects=True)
        return r.url
    except Exception as e:
        print(f"    no pude seguir el redirect: {e}", file=sys.stderr)
        return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--canal", required=True, choices=sorted(CUENTAS))
    p.add_argument("--dry-run", action="store_true", help="no escribe en la base")
    args = p.parse_args()

    load_dotenv(BOT / ".env")
    var_app, var_sec = CUENTAS[args.canal]
    app, sec = os.getenv(var_app), os.getenv(var_sec)
    if not app or not sec:
        sys.exit(f"Faltan {var_app} y {var_sec} en el .env del bot.")

    store = VideosStore(DB)
    videos = store.listar(canal=args.canal, cuantos=200)
    print(f"canal {args.canal}: {len(videos)} videos\n")

    cambiados = 0
    for v in videos:
        print(f"  {v.titulo[:50]}")
        print(f"    viejo: {v.link}")
        destino = url_real(v.link)
        if not destino:
            continue
        nuevo = retag_shopee_url(destino, app, sec, subids=[])
        if not nuevo:
            print("    FALLO al generar el link nuevo", file=sys.stderr)
            continue
        # OJO: `generateShortLink` devuelve un shortlink NUEVO siempre, incluso
        # con las credenciales de la cuenta que ya era duena del link viejo. O sea
        # que desde aca no hay forma de saber de que cuenta era el link original:
        # el script no verifica nada, aplica lo que se le pide. Correrlo sobre un
        # canal que ya estaba bien no rompe (el link viejo sigue vivo y apuntando
        # a la misma cuenta), pero cambia links por gusto — usar --dry-run primero.
        print(f"    NUEVO: {nuevo}")
        if not args.dry_run:
            store.registrar(
                v.item_id, canal=v.canal, titulo=v.titulo, link=nuevo,
                precio=v.precio, comision_pct=v.comision_pct,
                herramienta=v.herramienta, marca=v.marca, archivo=v.archivo,
                now=v.ts,   # la fecha es la del video, no la del re-tagueo
            )
        cambiados += 1

    print(f"\n{'(dry-run) ' if args.dry_run else ''}links regenerados: {cambiados}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
