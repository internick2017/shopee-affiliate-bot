"""De donde vinieron las ventas: por origen (Shopee Video, WhatsApp, sitio...) y por
etiqueta (subId) de las dos cuentas, con lo que vendio cada producto.

Uso (desde la raiz del repo):
    python scripts/video/ventas_origen.py            # ultimos 90 dias (lo maximo de la API)
    python scripts/video/ventas_origen.py --dias 7

`referrer` lo pone Shopee (Shopeevideo-Shopee, WhatsApp, Websites, Others). La etiqueta
sale de `utmContent` (los subIds unidos por guiones): `setupjusto` = sitio,
`setupjusto-youtube` / `setupjusto-facebook`, `tiktok-<post>`. "----" = link sin
etiqueta. "con video nuestro" = el producto vendido tiene video en `videos_producidos`.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv  # noqa: E402

from src.panel_sync import leer_conversiones  # noqa: E402
from src.video_canal import credenciales  # noqa: E402


def etiqueta(utm: str | None) -> str:
    partes = [p for p in (utm or "").split("-") if p]
    return "-".join(partes) or "sin etiqueta"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dias", type=int, default=90)
    args = ap.parse_args()
    load_dotenv(RAIZ / ".env")
    db = sqlite3.connect(RAIZ / "grabados.db")
    con_video = {int(i) for (i,) in db.execute("SELECT item_id FROM videos_producidos")}
    hasta = int(time.time())
    desde = hasta - min(args.dias, 90) * 86400 + 60
    for cuenta in ("lanny", "nick"):
        nodos, error = leer_conversiones(*credenciales(cuenta), desde=desde, hasta=hasta)
        origen: dict[str, list[float]] = defaultdict(lambda: [0, 0.0])
        tags: dict[str, list[float]] = defaultdict(lambda: [0, 0.0])
        productos: Counter[str] = Counter()
        video: Counter[str] = Counter()
        for n in nodos:
            ref = n.get("referrer") or "?"
            for o in n.get("orders") or []:
                for it in o.get("items") or []:
                    if "CANCEL" in (it.get("displayItemStatus") or ""):
                        continue
                    com = float(it.get("itemTotalCommission") or 0)
                    origen[ref][0] += 1
                    origen[ref][1] += com
                    tag = etiqueta(n.get("utmContent"))
                    tags[tag][0] += 1
                    tags[tag][1] += com
                    productos[f"{it.get('itemName', '')[:55]} ({ref})"] += 1
                    if ref.startswith("Shopeevideo"):
                        video["con video nuestro" if int(it.get("itemId") or 0) in con_video else "otro"] += 1
        print(f"\n== {cuenta.upper()}  ({datetime.fromtimestamp(desde):%d/%m} a hoy, sin cancelados)"
              + (f"  OJO: lectura incompleta: {error}" if error else ""))
        print("Por origen:")
        for k, (q, c) in sorted(origen.items(), key=lambda x: -x[1][1]):
            print(f"  {k:28} {int(q):4} ventas  R$ {c:8.2f}")
        print("Por etiqueta:")
        for k, (q, c) in sorted(tags.items(), key=lambda x: -x[1][1]):
            print(f"  {k:28} {int(q):4} ventas  R$ {c:8.2f}")
        print("Shopee Video:", dict(video))
        print("Lo que mas vendio:")
        for nombre, q in productos.most_common(8):
            print(f"  {q:3}  {nombre}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
