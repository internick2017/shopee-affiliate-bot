"""Ideas de productos para el panel de reportes.

Salen del muestreo (`run_snapshot.py`), que ya baja los productos de cada
categoria: no cuestan llamadas extra a la API. Son dos listas. "Mais vendidos"
sirve para pasar links: lo que mas vende, que es tambien lo que todos publican.
"Em alta" sirve para grabar: lo poco vendido, bien calificado, que vende ahora.
El panel las muestra en la pestana Ideias y descarta ahi las que cada canal ya
grabo.
"""

import statistics
from datetime import datetime
from typing import Any

from src.product_ideas import NOMBRES, Idea, _a_idea, _variar, retorno_por_venta
from src.trend_store import Tendencia

POR_CATEGORIA = 15

# Lo que hace falta para estar "em alta", ademas de vender menos que la mitad de
# su categoria. Sin dato de cuantas resenas tiene un producto, las ventas
# recientes son las que respaldan la calificacion.
RECIENTES_MINIMO = 30
RATING_MINIMO = 4.7
RETORNO_MINIMO = 1.0     # R$ por venta: por debajo, un video no se paga solo


def _ideas_de(nodos: list[dict]) -> tuple[list[Idea], dict[int, str | None]]:
    """Las ideas de una categoria y el link de producto de cada una. El link de
    oferta viene monetizado con la cuenta que hizo el pedido; el panel lo ven dos
    cuentas, asi que va el del producto, sin dueno."""
    ideas = [i for i in (_a_idea(n) for n in nodos) if i is not None]
    del_producto = {int(n["itemId"]): n.get("productLink") for n in nodos if n.get("itemId")}
    return ideas, del_producto


def _fila(i: Idea, cat_id: int, vista_en: datetime, **propias: Any) -> dict:
    return {
        "item_id": i.item_id,
        "categoria_id": cat_id,
        "categoria": NOMBRES.get(cat_id, str(cat_id)),
        "titulo": i.titulo,
        "precio": float(i.precio),
        "precio_min": None if i.precio_min is None else float(i.precio_min),
        "precio_max": None if i.precio_max is None else float(i.precio_max),
        "ventas": i.ventas,
        "comision_pct": float(i.comision_pct),
        "rating": float(i.rating),
        "descuento_pct": i.descuento_pct,
        "imagen_url": i.imagen_url,
        "vista_en": vista_en.isoformat(),
        **propias,
    }


def filas_de_ideas(
    nodos_por_categoria: dict[int, list[dict]],
    ventas_por_dia: dict[int, float],
    *,
    vista_en: datetime,
    por_categoria: int = POR_CATEGORIA,
) -> list[dict]:
    """Los mas vendidos: las mejores de cada categoria por puntaje, sin repetir el
    mismo producto con otro nombre."""
    filas: dict[int, dict] = {}
    for cat_id, nodos in nodos_por_categoria.items():
        ideas, del_producto = _ideas_de(nodos)
        ideas.sort(key=lambda i: i.puntaje, reverse=True)
        for i in _variar(ideas, por_categoria):
            por_dia = ventas_por_dia.get(i.item_id)
            filas[i.item_id] = _fila(
                i, cat_id, vista_en,
                tipo="mais_vendidos",
                ventas_por_dia=None if por_dia is None else round(por_dia, 2),
                ventas_recentes=None,
                link=del_producto.get(i.item_id) or i.link,
                puntaje=round(i.puntaje, 4),
            )
    return list(filas.values())


def filas_em_alta(
    nodos_por_categoria: dict[int, list[dict]],
    recientes: dict[int, Tendencia],
    *,
    vista_en: datetime,
    por_categoria: int = POR_CATEGORIA,
) -> list[dict]:
    """Lo que esta despegando: vendio menos que la mitad de su categoria, pero
    vende ahora, esta bien calificado y deja algo por venta. Ordenado por la parte
    de sus ventas que es reciente, que aca hace de puntaje. Si pocos cumplen, van
    solo esos: rellenar le quitaria el sentido a la lista."""
    filas: dict[int, dict] = {}
    for cat_id, nodos in nodos_por_categoria.items():
        ideas, del_producto = _ideas_de(nodos)
        if not ideas:
            continue
        mediana = statistics.median(i.ventas for i in ideas)
        candidatas = []
        for i in ideas:
            t = recientes.get(i.item_id)
            if (
                t is not None
                and t.nuevas >= RECIENTES_MINIMO
                and 0 < i.ventas < mediana
                and float(i.rating) >= RATING_MINIMO
                and retorno_por_venta(float(i.precio), float(i.comision_pct)) >= RETORNO_MINIMO
            ):
                candidatas.append((min(t.nuevas / i.ventas, 1.0), i, t))
        candidatas.sort(key=lambda c: c[0], reverse=True)
        for parte, i, t in candidatas[:por_categoria]:
            filas[i.item_id] = _fila(
                i, cat_id, vista_en,
                tipo="em_alta",
                ventas_por_dia=round(t.por_dia, 2),
                ventas_recentes=t.nuevas,
                link=del_producto.get(i.item_id) or i.link,
                puntaje=round(parte, 4),
            )
    return list(filas.values())


def subir_ideas(db: Any, filas: list[dict], *, vista_en: datetime) -> int:
    """Reemplaza las ideas del panel por las de hoy. Sin filas no toca nada: si la
    API de Shopee fallo, las de ayer siguen sirviendo."""
    if not filas:
        return 0
    db.upsert("ideia", filas, "item_id,tipo")
    db.borrar_anteriores("ideia", "vista_en", vista_en.isoformat())
    return len(filas)
