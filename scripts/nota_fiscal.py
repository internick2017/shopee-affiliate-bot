"""Valores de las notas fiscales de la factura mensual de Shopee, de las dos cuentas.

Uso (desde la raiz del repo):
    python scripts/nota_fiscal.py               # el mes pasado (lo que Shopee factura el dia 1)
    python scripts/nota_fiscal.py --mes 2026-10

Muestra, por cuenta, el valor de la nota contra SHPS Tecnologia y el de cada tienda.
El valor que manda es el que pide la app (Renda, Historico de Pagamento): si no
coincide, avisar a Nick antes de emitir. Pasos completos en la skill nota-fiscal-mensal.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv  # noqa: E402

from src.nota_fiscal import CAMPOS, limites_del_mes, partes  # noqa: E402
from src.panel_sync import leer_conversiones  # noqa: E402
from src.video_canal import credenciales  # noqa: E402


def brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "x").replace(".", ",").replace("x", ".")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mes", help="AAAA-MM; por defecto el mes pasado")
    args = ap.parse_args()
    if args.mes:
        anio, mes = map(int, args.mes.split("-"))
    else:
        hoy = date.today()
        anio, mes = (hoy.year, hoy.month - 1) if hoy.month > 1 else (hoy.year - 1, 12)
    load_dotenv(RAIZ / ".env")
    desde, hasta = limites_del_mes(anio, mes)
    fallo = False
    for cuenta in ("lanny", "nick"):
        nodos, error = leer_conversiones(*credenciales(cuenta), desde=desde, hasta=hasta,
                                         por="completeTime", campos=CAMPOS)
        p = partes(nodos, desde, hasta)
        print(f"\n{cuenta} {anio}-{mes:02d}: total {brl(p.total)}")
        if error:
            fallo = True
            print(f"  INCOMPLETO: {error}")
        print(f"  Nota a SHPS Tecnologia (35.635.824/0001-12): {brl(p.shopee)}")
        for tienda, valor in p.por_tienda.items():
            print(f"  Tienda {tienda}: {brl(valor)} (nota solo si la pide)")
    return 1 if fallo else 0


if __name__ == "__main__":
    raise SystemExit(main())
