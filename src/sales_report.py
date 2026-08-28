"""Qué se vendió de verdad con los links del canal, leído de `conversionReport`.

Existe para cerrar el circuito: `product_ideas` decide qué grabar con una fórmula,
y esto dice si esa fórmula acierta. Sin este lado, el ranking es una teoría que
nunca se contrasta.

Dos decisiones de lectura, tomadas mirando los datos reales (90 días, 2026-08-28):

  - Solo cuentan los items COMPLETED. En la muestra real había 73 completados, 14
    cancelados y 6 pendientes: contar los cancelados infla la comisión con plata
    que no llegó.
  - Se agrupa por BANDA DE PRECIO, no por producto. Casi todos los productos
    vendieron una sola unidad (82 productos distintos en 75 conversiones), así que
    a nivel producto no hay patrón que aprender; la señal aparece al agregar.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from .shopee_resolver import _graphql_call

_ESTADO_VALIDO = "COMPLETED"

# Bordes de las bandas de precio, en reales. El último tramo es abierto.
_BANDAS: tuple[tuple[float, float, str], ...] = (
    (0, 20, "hasta R$20"),
    (20, 50, "R$20-50"),
    (50, 80, "R$50-80"),
    (80, 150, "R$80-150"),
    (150, float("inf"), "mas de R$150"),
)


@dataclass
class Banda:
    etiqueta: str
    items: int = 0
    comision: float = 0.0

    @property
    def por_item(self) -> float:
        return self.comision / self.items if self.items else 0.0


@dataclass
class Ventas:
    """Resumen del período. `error` presente = el resto sin sentido."""

    dias: int = 0
    completados: int = 0
    cancelados: int = 0
    pendientes: int = 0
    comision: float = 0.0
    bandas: list[Banda] = field(default_factory=list)
    top: list[tuple[str, float]] = field(default_factory=list)
    error: str | None = None

    @property
    def por_venta(self) -> float:
        return self.comision / self.completados if self.completados else 0.0


_CAMPOS = (
    "conversionReport(purchaseTimeStart:%d,purchaseTimeEnd:%d,limit:%d)"
    "{nodes{orders{items{itemName itemPrice qty itemTotalCommission displayItemStatus}}}}"
)


def resumen_ventas(
    app_id: str,
    secret: str,
    *,
    dias: int = 30,
    limite: int = 100,
    ahora: int | None = None,
    http_post: Callable[..., object] | None = None,
) -> Ventas:
    """Resumen de los últimos `dias`. `ahora` se inyecta en los tests para que el
    resultado no dependa del reloj."""
    fin = int(ahora if ahora is not None else time.time())
    ini = fin - dias * 86400
    query = "{%s}" % (_CAMPOS % (ini, fin, max(1, min(limite, 500))))
    kwargs = {"http_post": http_post} if http_post is not None else {}
    data = _graphql_call(app_id, secret, query, **kwargs)
    if not data:
        return Ventas(dias=dias, error="No pude leer el reporte de ventas de Shopee.")

    nodos = ((data.get("conversionReport") or {}).get("nodes")) or []
    v = Ventas(dias=dias)
    bandas = {e: Banda(e) for _lo, _hi, e in _BANDAS}
    por_producto: dict[str, float] = {}

    for nodo in nodos:
        for orden in nodo.get("orders") or []:
            for item in orden.get("items") or []:
                estado = item.get("displayItemStatus")
                if estado == "CANCELLED":
                    v.cancelados += 1
                    continue
                if estado != _ESTADO_VALIDO:
                    v.pendientes += 1
                    continue
                try:
                    precio = float(item.get("itemPrice") or 0)
                    com = float(item.get("itemTotalCommission") or 0)
                except (TypeError, ValueError):
                    continue
                v.completados += 1
                v.comision += com
                nombre = (item.get("itemName") or "?")[:50]
                por_producto[nombre] = por_producto.get(nombre, 0.0) + com
                for lo, hi, etiqueta in _BANDAS:
                    if lo <= precio < hi:
                        bandas[etiqueta].items += 1
                        bandas[etiqueta].comision += com
                        break

    v.bandas = [b for b in bandas.values() if b.items]
    v.top = sorted(por_producto.items(), key=lambda kv: -kv[1])[:5]
    return v
