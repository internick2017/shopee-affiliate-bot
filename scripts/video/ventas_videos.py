"""Cruza los videos ya producidos contra las ventas reales de Shopee.

Responde la unica pregunta que importa despues de gastar puntos y creditos:
de los productos a los que les hice video, ¿cuales vendieron?

Junta dos piezas que ya existian y no se hablaban: `videos_producidos`
(grabados.db, lo que escribe la skill shopee-video-flow) y el `conversionReport`
de la Affiliate API, que trae `itemId` por conversion.

OJO CON LA CUENTA — es el error facil de cometer:

    El reporte de ventas es POR CUENTA DE AFILIADO. Nick y Lanny son cuentas
    distintas, con links distintos. Consultar la cuenta de Lanny y no encontrar un
    producto del canal de Nick NO significa que no vendio: significa que se miro
    en el lugar equivocado.

    Las credenciales del `.env` del bot son las de la cuenta de LANNY. Para el canal
    de Nick hay que pasar las suyas por parametro o por las variables de entorno
    SHOPEE_APP_ID_NICK / SHOPEE_SECRET_NICK.

Uso:
    python ventas_videos.py                    # cuenta del .env (Lanny)
    python ventas_videos.py --canal lanny      # solo los videos de ese canal
    python ventas_videos.py --canal nick --cuenta nick
    python ventas_videos.py --dias 60
"""

from __future__ import annotations

import argparse
import collections
import datetime
import io
import os
import sys
import time
from pathlib import Path

# La consola de Windows es cp1252 y los titulos de Shopee traen acentos: sin esto
# el script muere con UnicodeEncodeError a mitad del listado.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Este script vive en scripts/video/ del propio repo del bot.
BOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BOT))

from dotenv import load_dotenv  # noqa: E402

from src.grabados_store import VideosStore  # noqa: E402
from src.shopee_resolver import _graphql_call  # noqa: E402

DB = BOT / "grabados.db"


def credenciales(cuenta: str) -> tuple[str, str]:
    """`lanny` sale del .env del bot; `nick` de variables aparte, porque su cuenta
    de afiliado es otra (alta 2026-09-01, para setupjusto.com.br)."""
    load_dotenv(BOT / ".env")
    if cuenta == "nick":
        app, sec = os.getenv("SHOPEE_APP_ID_NICK"), os.getenv("SHOPEE_SECRET_NICK")
        if not app or not sec:
            sys.exit(
                "Faltan las credenciales de la cuenta de Nick.\n"
                "Definí SHOPEE_APP_ID_NICK y SHOPEE_SECRET_NICK (podés agregarlas\n"
                "al .env del bot) y volvé a correr. Sin eso, el reporte que sale es\n"
                "el de la cuenta de Lanny y no dice nada sobre el canal de Nick."
            )
        return app, sec
    return os.getenv("SHOPEE_APP_ID", ""), os.getenv("SHOPEE_SECRET", "")


def ventas_por_item(app: str, sec: str, dias: int) -> dict[int, dict]:
    fin = int(time.time())
    ini = fin - dias * 86400
    query = (
        "{conversionReport(purchaseTimeStart:%d,purchaseTimeEnd:%d,limit:500)"
        "{nodes{referrer orders{items{itemId itemName qty itemPrice "
        "itemTotalCommission displayItemStatus completeTime}}}}}" % (ini, fin)
    )
    data = _graphql_call(app, sec, query)
    nodos = ((data or {}).get("conversionReport") or {}).get("nodes") or []
    out: dict[int, dict] = {}
    for nodo in nodos:
        ref = nodo.get("referrer") or "desconocido"
        for orden in nodo.get("orders") or []:
            for it in orden.get("items") or []:
                iid = int(it.get("itemId") or 0)
                e = out.setdefault(
                    iid,
                    dict(unidades=0, comision=0.0, estados=[], origenes=set(),
                         nombre=(it.get("itemName") or "")[:45], cuando=None),
                )
                e["estados"].append(it.get("displayItemStatus"))
                e["origenes"].add(ref)
                if it.get("displayItemStatus") == "COMPLETED":
                    e["unidades"] += int(it.get("qty") or 1)
                    e["comision"] += float(it.get("itemTotalCommission") or 0)
                    if it.get("completeTime"):
                        e["cuando"] = int(it["completeTime"])
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--canal", choices=["nick", "lanny"], help="filtrar los videos")
    p.add_argument("--cuenta", choices=["nick", "lanny"], default="lanny",
                   help="de que cuenta de afiliado leer las ventas (default: lanny)")
    p.add_argument("--dias", type=int, default=30)
    args = p.parse_args()

    if args.canal and args.canal != args.cuenta:
        print(f"AVISO: mirando videos del canal '{args.canal}' contra las ventas de "
              f"la cuenta '{args.cuenta}'. Son cuentas distintas: los links de un "
              f"canal no aparecen en el reporte del otro.\n", file=sys.stderr)

    app, sec = credenciales(args.cuenta)
    ventas = ventas_por_item(app, sec, args.dias)
    videos = VideosStore(DB).listar(canal=args.canal, cuantos=200)

    print(f"cuenta consultada: {args.cuenta} | ultimos {args.dias} dias")
    print(f"productos distintos con conversiones: {len(ventas)}\n")

    con_venta = 0
    for v in videos:
        f = datetime.datetime.fromtimestamp(v.ts).strftime("%d/%m")
        e = ventas.get(v.item_id)
        if e and e["unidades"]:
            con_venta += 1
            org = ",".join(sorted(e["origenes"]))
            print(f"  VENDIO   {f} {v.canal:6} {v.titulo[:34]:34} "
                  f"{e['unidades']}u  R${e['comision']:6.2f}  ({org})")
        elif e:
            print(f"  cancel.  {f} {v.canal:6} {v.titulo[:34]:34} {e['estados']}")
        else:
            print(f"    -      {f} {v.canal:6} {v.titulo[:34]}")

    print(f"\ncon venta: {con_venta} de {len(videos)} videos")

    org = collections.defaultdict(lambda: [0, 0.0])
    for e in ventas.values():
        if e["unidades"]:
            for o in e["origenes"]:
                org[o][0] += e["unidades"]
                org[o][1] += e["comision"]
    if org:
        print("\n=== todas las ventas de la cuenta, por origen ===")
        for o, (n, c) in sorted(org.items(), key=lambda x: -x[1][0]):
            print(f"  {o:22} {n:3} items   R${c:7.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
