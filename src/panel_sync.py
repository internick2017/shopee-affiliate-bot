"""Copia las ventas de Shopee y los videos grabados al panel de reportes (Supabase).

El panel se abre desde el celular, pero las claves de Shopee y `grabados.db` viven
en esta PC. Este modulo es el puente: lee de aca y escribe alla. El panel solo lee.
Diseno completo: docs/superpowers/specs/2026-10-02-panel-reportes-design.md.

Esta parte es pura (sin red): convierte lo que devuelve la API de Shopee y lo que
guarda `VideosStore` en filas con los nombres de columna de las tablas `venta` y
`video` del panel.
"""

from __future__ import annotations

from datetime import UTC, datetime

from .grabados_store import VideoProducido

# Setup Justo es de Nick: sus videos van a su cuenta, separados por `canal`.
CUENTA_DE_CANAL: dict[str, str] = {"lanny": "lanny", "nick": "nick", "setupjusto": "nick"}


def _iso(ts: float | int | None) -> str | None:
    """Fecha ISO en UTC. Shopee manda 0 (no null) en `completeTime` de una venta
    que todavia no se completo: 0 tambien es "sin fecha", no el 1/1/1970."""
    if not ts:
        return None
    return datetime.fromtimestamp(float(ts), UTC).isoformat()


def filas_de_ventas(cuenta: str, nodos: list[dict], *, vista_en: datetime) -> list[dict]:
    """Una fila de `venta` por producto vendido. El origen (`referrer`) viene en la
    conversion, no en el item: un pedido entero vino de un solo lugar."""
    filas = []
    for nodo in nodos:
        for orden in nodo.get("orders") or []:
            for item in orden.get("items") or []:
                filas.append({
                    "cuenta": cuenta,
                    "conversion_id": int(nodo.get("conversionId") or 0),
                    "order_id": str(orden.get("orderId") or ""),
                    "item_id": int(item.get("itemId") or 0),
                    "model_id": int(item.get("modelId") or 0),
                    "clic_en": _iso(nodo.get("clickTime")),
                    "compra_en": _iso(nodo.get("purchaseTime")),
                    "completada_en": _iso(item.get("completeTime")),
                    "estado": item.get("displayItemStatus") or "",
                    "producto": item.get("itemName") or "",
                    "imagen_url": item.get("imageUrl") or None,
                    "categoria": item.get("categoryLv1Name") or None,
                    "precio": float(item.get("itemPrice") or 0),
                    "cantidad": int(item.get("qty") or 1),
                    "comision": float(item.get("itemTotalCommission") or 0),
                    "origen": nodo.get("referrer") or "desconocido",
                    "utm_content": nodo.get("utmContent") or None,
                    "vista_en": vista_en.isoformat(),
                })
    return filas


def filas_de_videos(videos: list[VideoProducido]) -> list[dict]:
    """Una fila de `video` por cada (canal, producto) de `grabados.db`."""
    return [
        {
            "canal": v.canal,
            "item_id": v.item_id,
            "cuenta": CUENTA_DE_CANAL[v.canal],
            "titulo": v.titulo,
            "link": v.link,
            "archivo": v.archivo,
            "herramienta": v.herramienta,
            "comision_pct": v.comision_pct,
            "precio": v.precio,
            "grabado_en": _iso(v.ts),
            "publicado_en": _iso(v.publicado_ts),
        }
        for v in videos
    ]
