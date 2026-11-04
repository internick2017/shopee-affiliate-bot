"""Cuanto va en cada nota fiscal de la factura mensual de Shopee.

El dia 1 Shopee factura lo que se completo el mes anterior y pide dos tipos de
nota: una contra Shopee (SHPS Tecnologia) por su parte de la comision, y una por
tienda por la parte que paga cada vendedor (solo si la tienda la pide).

Regla medida el 2026-11-03 contra la factura de octubre de Nick (R$ 12,90 de
Shopee y R$ 6,66 de BuddyShopping): items con `completeTime` dentro del mes y
`displayItemStatus` COMPLETED. Los cancelados vienen con comision 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

BRASIL = ZoneInfo("America/Sao_Paulo")

CAMPOS = (
    "nodes{orders{items{completeTime displayItemStatus shopName"
    " itemShopeeCommissionCapped itemSellerCommission}}}"
    " pageInfo{hasNextPage scrollId}"
)


@dataclass
class Partes:
    shopee: float = 0.0
    por_tienda: dict[str, float] = field(default_factory=dict)

    @property
    def total(self) -> float:
        return round(self.shopee + sum(self.por_tienda.values()), 2)


def limites_del_mes(anio: int, mes: int) -> tuple[int, int]:
    """Epoch del primer segundo del mes y del primero del mes siguiente, hora de Brasil."""
    ini = datetime(anio, mes, 1, tzinfo=BRASIL)
    fin = datetime(anio + mes // 12, mes % 12 + 1, 1, tzinfo=BRASIL)
    return int(ini.timestamp()), int(fin.timestamp())


def partes(nodos: list[dict], desde: int, hasta: int) -> Partes:
    """Suma de la comision de Shopee y de cada tienda, redondeada a centavos al final
    (la API manda fracciones: 0.99945 + 3.9528 + 4.17 + 3.7761 = 12,90)."""
    shopee = 0.0
    tiendas: dict[str, float] = {}
    for nodo in nodos:
        for orden in nodo.get("orders") or []:
            for item in orden.get("items") or []:
                if item.get("displayItemStatus") != "COMPLETED":
                    continue
                if not desde <= (item.get("completeTime") or 0) < hasta:
                    continue
                shopee += float(item.get("itemShopeeCommissionCapped") or 0)
                vendedor = float(item.get("itemSellerCommission") or 0)
                if vendedor:
                    tienda = item.get("shopName") or "?"
                    tiendas[tienda] = tiendas.get(tienda, 0.0) + vendedor
    return Partes(round(shopee, 2), {t: round(v, 2) for t, v in sorted(tiendas.items())})
