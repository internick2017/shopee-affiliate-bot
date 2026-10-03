"""Ideas de productos para el panel de reportes.

Salen del muestreo diario (`run_snapshot.py`), que ya baja los mas vendidos de
cada categoria: no cuestan llamadas extra a la API. El panel las muestra en la
pestana Ideias y descarta ahi las que cada canal ya grabo.
"""

from datetime import datetime
from typing import Any

from src.product_ideas import NOMBRES, _a_idea, _variar

POR_CATEGORIA = 15


def filas_de_ideas(
    nodos_por_categoria: dict[int, list[dict]],
    ventas_por_dia: dict[int, float],
    *,
    vista_en: datetime,
    por_categoria: int = POR_CATEGORIA,
) -> list[dict]:
    """Una fila de `ideia` por producto: las mejores de cada categoria por puntaje,
    sin repetir el mismo producto con otro nombre."""
    filas: dict[int, dict] = {}
    for cat_id, nodos in nodos_por_categoria.items():
        # El link de oferta viene monetizado con la cuenta que hizo el pedido. El
        # panel lo ven dos cuentas, asi que va el del producto, sin dueno.
        del_producto = {str(n.get("itemId")): n.get("productLink") for n in nodos}
        ideas = [i for i in (_a_idea(n) for n in nodos) if i is not None]
        ideas.sort(key=lambda i: i.puntaje, reverse=True)
        for i in _variar(ideas, por_categoria):
            por_dia = ventas_por_dia.get(i.item_id)
            filas[i.item_id] = {
                "item_id": i.item_id,
                "categoria_id": cat_id,
                "categoria": NOMBRES.get(cat_id, str(cat_id)),
                "titulo": i.titulo,
                "precio": float(i.precio),
                "precio_min": None if i.precio_min is None else float(i.precio_min),
                "precio_max": None if i.precio_max is None else float(i.precio_max),
                "ventas": i.ventas,
                "ventas_por_dia": None if por_dia is None else round(por_dia, 2),
                "comision_pct": float(i.comision_pct),
                "rating": float(i.rating),
                "descuento_pct": i.descuento_pct,
                "imagen_url": i.imagen_url,
                "link": del_producto.get(str(i.item_id)) or i.link,
                "puntaje": round(i.puntaje, 4),
                "vista_en": vista_en.isoformat(),
            }
    return list(filas.values())


def subir_ideas(db: Any, filas: list[dict], *, vista_en: datetime) -> int:
    """Reemplaza las ideas del panel por las de hoy. Sin filas no toca nada: si la
    API de Shopee fallo, las de ayer siguen sirviendo."""
    if not filas:
        return 0
    db.upsert("ideia", filas, "item_id")
    db.borrar_anteriores("ideia", "vista_en", vista_en.isoformat())
    return len(filas)
