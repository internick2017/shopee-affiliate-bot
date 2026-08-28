"""Muestreo diario de ventas por producto, insumo del detector de tendencia.

Corre una vez por día (ver el .vbs / tarea programada). Recorre las categorías
mapeadas, pide los productos más vendidos de cada una y guarda su `sales` de hoy.

La derivada entre días es lo que dice qué está DESPEGANDO, que es distinto de lo
que ya vendió mucho — ver el docstring de `src/trend_store.py`.

Uso:
    python run_snapshot.py            # todas las categorías
    python run_snapshot.py beleza     # solo una
"""

import logging
import sys
import time

from src.config import load_config
from src.product_ideas import CATEGORIAS, _CAMPOS, NOMBRES, resolver_categoria
from src.shopee_resolver import _graphql_call
from src.trend_store import TrendStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("snapshot")

_POR_CATEGORIA = 50      # techo de la API
_PAUSA = 1.5             # segundos entre llamadas: la API tiene rate limit (10030)


def _muestrear(app_id: str, secret: str, cat_id: int) -> list[dict]:
    query = "{productOfferV2(productCatId:%d,sortType:2,limit:%d){nodes{%s}}}" % (
        cat_id, _POR_CATEGORIA, _CAMPOS,
    )
    data = _graphql_call(app_id, secret, query)
    if not data:
        return []
    return ((data.get("productOfferV2") or {}).get("nodes")) or []


def main() -> None:
    cfg = load_config()
    if not cfg["shopee_app_id"] or not cfg["shopee_secret"]:
        logger.error("Falta SHOPEE_APP_ID/SHOPEE_SECRET en el .env.")
        return

    store = TrendStore(cfg.get("trend_db", "tendencias.db"))

    if len(sys.argv) > 1:
        cat_id = resolver_categoria(sys.argv[1])
        if cat_id is None:
            logger.error("No conozco la categoria %r. Opciones: %s",
                         sys.argv[1], ", ".join(sorted(CATEGORIAS)))
            return
        objetivos = [cat_id]
    else:
        objetivos = sorted(set(CATEGORIAS.values()))

    guardados = 0
    for i, cat_id in enumerate(objetivos, 1):
        nodos = _muestrear(cfg["shopee_app_id"], cfg["shopee_secret"], cat_id)
        for n in nodos:
            try:
                store.registrar(
                    int(n["itemId"]),
                    int(n.get("sales") or 0),
                    titulo=n.get("productName") or "",
                    precio=float(n.get("price") or 0),
                    comision_pct=float(n.get("commissionRate") or 0) * 100,
                    link=n.get("offerLink") or "",
                )
                guardados += 1
            except (KeyError, TypeError, ValueError):
                continue
        logger.info("[%d/%d] %s: %d productos", i, len(objetivos),
                    NOMBRES.get(cat_id, cat_id), len(nodos))
        time.sleep(_PAUSA)

    logger.info("Listo: %d muestras guardadas. Dias con datos: %d",
                guardados, store.dias_con_datos())


if __name__ == "__main__":
    main()
