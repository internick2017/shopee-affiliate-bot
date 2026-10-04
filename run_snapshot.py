"""Muestreo de ventas y precios por producto, insumo del detector de tendencia.

Corre cada hora (tarea programada "Muestreo Shopee", que lanza muestreo-diario.vbs).
Recorre las categorías mapeadas, pide los productos más vendidos de cada una y
guarda su `sales` y su precio de hoy: las corridas del mismo día pisan la muestra
anterior. De paso avisa por Telegram las caídas de precio.

La primera corrida del día además baja páginas más profundas de cada categoría,
donde está lo poco vendido, y sube las ideas al panel.

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
from src.panel_ideas import filas_de_ideas, filas_em_alta, subir_ideas
from src.panel_sync import Supabase
from src.price_alerts import avisar_caidas, detectar_caidas, enviar_telegram
from src.product_ideas import CATEGORIAS, _CAMPOS, NOMBRES, resolver_categoria
from src.shopee_resolver import _graphql_call
from src.trend_store import Muestra, TrendStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("snapshot")

_POR_CATEGORIA = 50      # techo de la API
_PAUSA = 1.5             # segundos entre llamadas: la API tiene rate limit (10030)
# La pagina 1 son los mas vendidos. Las otras dos se piden solo para armar las
# ideas: ahi abajo esta lo poco vendido, de donde sale la lista "em alta".
_PAGINAS_PARA_IDEAS = (1, 5, 10)
_VENTANA_RECIENTE = 30   # dias que cuentan como "ventas recientes"


def _muestrear(app_id: str, secret: str, cat_id: int, pagina: int) -> list[dict]:
    query = (
        "{productOfferV2(productCatId:%d,sortType:2,page:%d,limit:%d){nodes{%s productLink}}}"
        % (cat_id, pagina, _POR_CATEGORIA, _CAMPOS)
    )
    data = _graphql_call(app_id, secret, query)
    if not data:
        return []
    return ((data.get("productOfferV2") or {}).get("nodes")) or []


def _a_muestra(nodo: dict) -> Muestra | None:
    """Un nodo de productOfferV2 como muestra. None si viene sin itemId o con datos rotos."""
    try:
        return Muestra(
            item_id=int(nodo["itemId"]),
            ventas=int(nodo.get("sales") or 0),
            titulo=nodo.get("productName") or "",
            precio=float(nodo.get("price") or 0),
            comision_pct=float(nodo.get("commissionRate") or 0) * 100,
            link=nodo.get("offerLink") or "",
        )
    except (KeyError, TypeError, ValueError):
        return None


def _panel() -> Supabase | None:
    url, llave = os.getenv("SUPABASE_PANEL_URL"), os.getenv("SUPABASE_PANEL_SERVICE_KEY")
    return Supabase(url, llave) if url and llave else None


def _publicar_ideas(
    panel: Supabase,
    mas_vendidos: dict[int, list[dict]],
    todos: dict[int, list[dict]],
    store: TrendStore,
) -> None:
    """Sube las dos listas de ideas al panel y anota que hoy ya salieron. Nunca
    frena el muestreo: si Supabase falla se avisa, el muestreo queda guardado y la
    corrida siguiente lo vuelve a intentar."""
    ahora = datetime.now(UTC)
    por_dia = {t.item_id: t.por_dia for t in store.tendencias(minimo_nuevas=1)}
    recientes = {
        t.item_id: t
        for t in store.tendencias(ventana_dias=_VENTANA_RECIENTE, minimo_nuevas=1)
    }
    vendidos = filas_de_ideas(mas_vendidos, por_dia, vista_en=ahora)
    em_alta = filas_em_alta(todos, recientes, vista_en=ahora)
    try:
        subir_ideas(panel, vendidos + em_alta, vista_en=ahora)
    except Exception as exc:  # noqa: BLE001
        logger.error("No pude subir las ideas al panel: %s", exc)
        return
    store.marcar_ideas_publicadas()
    logger.info("Ideas en el panel: %d mais vendidos, %d em alta", len(vendidos), len(em_alta))


def _alertar_caidas(nodos: list[dict], store: TrendStore, token: str | None) -> None:
    """Avisa por Telegram de los productos cuyo precio cayo fuerte contra sus dias
    previos. Sin ALERTAS_CHAT_ID solo las cuenta en el log."""
    caidas = detectar_caidas(nodos, store.precios_de_referencia())
    chat = os.getenv("ALERTAS_CHAT_ID")
    if not token or not chat:
        logger.info("Caidas de precio: %d. Sin TELEGRAM_BOT_TOKEN o ALERTAS_CHAT_ID no se envian.",
                    len(caidas))
        return
    enviadas = avisar_caidas(caidas, store, lambda texto: enviar_telegram(token, chat, texto))
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

    # Con una sola categoria pedida, subir borraria del panel las ideas de las demas.
    panel = _panel() if len(sys.argv) == 1 else None
    con_ideas = panel is not None and not store.ideas_publicadas_hoy()
    paginas = _PAGINAS_PARA_IDEAS if con_ideas else (1,)

    guardados = 0
    mas_vendidos: dict[int, list[dict]] = {}
    todos: dict[int, list[dict]] = {}
    for i, cat_id in enumerate(objetivos, 1):
        por_pagina = []
        for pagina in paginas:
            por_pagina.append(_muestrear(cfg["shopee_app_id"], cfg["shopee_secret"], cat_id, pagina))
            time.sleep(_PAUSA)
        mas_vendidos[cat_id] = por_pagina[0]
        todos[cat_id] = [n for nodos in por_pagina for n in nodos]
        muestras = [m for n in todos[cat_id] if (m := _a_muestra(n))]
        store.registrar_muestras(muestras)
        guardados += len(muestras)
        logger.info("[%d/%d] %s: %d productos", i, len(objetivos),
                    NOMBRES.get(cat_id, cat_id), len(muestras))

    logger.info("Listo: %d muestras guardadas. Dias con datos: %d",
                guardados, store.dias_con_datos())
    _alertar_caidas([n for nodos in todos.values() for n in nodos],
                    store, cfg.get("telegram_bot_token"))
    if con_ideas:
        _publicar_ideas(panel, mas_vendidos, todos, store)


if __name__ == "__main__":
    main()
