"""Alertas de caida de precio ("bugs" de oferta).

La API de Shopee da el precio de hoy, no su historia. La historia es la del
muestreo diario (`TrendStore`): un producto alerta cuando su precio de hoy cae
fuerte contra la mediana de sus dias previos.

El precio que da la API es el de la variacion mas barata, asi que una variacion
nueva y barata tambien dispara la alerta. Por eso el mensaje pide conferir.
"""

from dataclasses import dataclass
from typing import Any

import requests

MINIMO_PCT = 40.0
# Por debajo de esto una caida grande en porcentaje son centavos.
PRECIO_ANTES_MINIMO = 20.0


@dataclass(frozen=True)
class Caida:
    item_id: int
    titulo: str
    precio_antes: float
    precio_ahora: float
    comision_pct: float
    link: str

    @property
    def pct(self) -> float:
        return round((1 - self.precio_ahora / self.precio_antes) * 100, 1)


def detectar_caidas(
    nodos: list[dict],
    referencia: dict[int, float],
    *,
    minimo_pct: float = MINIMO_PCT,
    precio_antes_minimo: float = PRECIO_ANTES_MINIMO,
) -> list[Caida]:
    """Productos cuyo precio de hoy cayo al menos `minimo_pct` contra su referencia,
    de la caida mas grande a la mas chica."""
    caidas = []
    for n in nodos:
        try:
            item_id = int(n["itemId"])
            ahora = float(n.get("price") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        antes = referencia.get(item_id)
        if not antes or antes < precio_antes_minimo or ahora <= 0:
            continue
        c = Caida(
            item_id=item_id, titulo=n.get("productName") or str(item_id),
            precio_antes=antes, precio_ahora=ahora,
            comision_pct=float(n.get("commissionRate") or 0) * 100,
            link=n.get("offerLink") or "",
        )
        if c.pct >= minimo_pct:
            caidas.append(c)
    caidas.sort(key=lambda c: c.pct, reverse=True)
    return caidas


def _reais(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def texto_alerta(c: Caida) -> str:
    return (
        f"📉 Queda de preço: -{c.pct:g}%\n"
        f"{c.titulo}\n"
        f"De {_reais(c.precio_antes)} por {_reais(c.precio_ahora)} "
        f"(comissão {c.comision_pct:g}%)\n"
        "Conferir as variações antes de divulgar: o preço é o da mais barata.\n"
        f"{c.link}"
    )


def enviar_telegram(token: str, chat_id: int | str, texto: str, *, http: Any = requests) -> None:
    """Manda un mensaje por la Bot API. El token nunca aparece en el error."""
    r = http.post(f"https://api.telegram.org/bot{token}/sendMessage",
                  json={"chat_id": chat_id, "text": texto}, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"Telegram rechazo el mensaje ({r.status_code}): {r.text[:200]}")
