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
import os
import sys
import time
from datetime import UTC, datetime

from src.config import load_config
from src.panel_ideas import filas_de_ideas, subir_ideas
from src.panel_sync import Supabase
from src.price_alerts import detectar_caidas, enviar_telegram, texto_alerta
from src.product_ideas import CATEGORIAS, _CAMPOS, NOMBRES, resolver_categoria
from src.shopee_resolver import _graphql_call
from src.trend_store import TrendStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("snapshot")

_POR_CATEGORIA = 50      # techo de la API
_PAUSA = 1.5             # segundos entre llamadas: la API tiene rate limit (10030)


def _muestrear(app_id: str, secret: str, cat_id: int) -> list[dict]:
    query = "{productOfferV2(productCatId:%d,sortType:2,limit:%d){nodes{%s productLink}}}" % (
        cat_id, _POR_CATEGORIA, _CAMPOS,
    )
    data = _graphql_call(app_id, secret, query)
    if not data:
        return []
    return ((data.get("productOfferV2") or {}).get("nodes")) or []


def _publicar_ideas(nodos_por_categoria: dict[int, list[dict]], store: TrendStore) -> None:
    """Sube las ideas del dia al panel. Nunca frena el muestreo: sin las llaves del
    panel, o si Supabase falla, se avisa y el muestreo queda guardado igual."""
    url, llave = os.getenv("SUPABASE_PANEL_URL"), os.getenv("SUPABASE_PANEL_SERVICE_KEY")
    if not url or not llave:
        logger.info("Sin llaves del panel en el .env: no se suben ideas.")
        return
    ahora = datetime.now(UTC)
    por_dia = {t.item_id: t.por_dia for t in store.tendencias(minimo_nuevas=1)}
    filas = filas_de_ideas(nodos_por_categoria, por_dia, vista_en=ahora)
    try:
        subidas = subir_ideas(Supabase(url, llave), filas, vista_en=ahora)
    except Exception as exc:  # noqa: BLE001
        logger.error("No pude subir las ideas al panel: %s", exc)
        return
    logger.info("Ideas en el panel: %d", subidas)


def _alertar_caidas(nodos: list[dict], store: TrendStore, token: str | None) -> None:
    """Avisa por Telegram de los productos cuyo precio cayo fuerte contra sus dias
    previos. Sin ALERTAS_CHAT_ID solo las anota en el log, sin marcarlas: asi salen
    el dia que se configure el destino."""
    caidas = detectar_caidas(nodos, store.precios_de_referencia())
    chat = os.getenv("ALERTAS_CHAT_ID")
    if not token or not chat:
        logger.info("Caidas de precio: %d. Sin TELEGRAM_BOT_TOKEN o ALERTAS_CHAT_ID no se envian.",
                    len(caidas))
        return
    enviadas = 0
    for c in caidas:
        if not store.marcar_alertado(c.item_id):
            continue
        try:
            enviar_telegram(token, chat, texto_alerta(c))
            enviadas += 1
        except Exception as exc:  # noqa: BLE001
            logger.error("No pude enviar la alerta de %s: %s", c.item_id, exc)
    logger.info("Caidas de precio: %d, alertas enviadas: %d", len(caidas), enviadas)


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
    nodos_por_categoria: dict[int, list[dict]] = {}
    for i, cat_id in enumerate(objetivos, 1):
        nodos = _muestrear(cfg["shopee_app_id"], cfg["shopee_secret"], cat_id)
        nodos_por_categoria[cat_id] = nodos
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
    _alertar_caidas([n for nodos in nodos_por_categoria.values() for n in nodos],
                    store, cfg.get("telegram_bot_token"))
    # Con una sola categoria pedida, subir borraria del panel las ideas de las demas.
    if len(sys.argv) == 1:
        _publicar_ideas(nodos_por_categoria, store)


if __name__ == "__main__":
    main()
