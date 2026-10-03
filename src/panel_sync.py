"""Copia las ventas de Shopee y los videos grabados al panel de reportes (Supabase).

El panel se abre desde el celular, pero las claves de Shopee y `grabados.db` viven
en esta PC. Este modulo es el puente: lee de aca y escribe alla. El panel solo lee.
Diseno completo: docs/superpowers/specs/2026-10-02-panel-reportes-design.md en el repo del panel.

Esta parte es pura (sin red): convierte lo que devuelve la API de Shopee y lo que
guarda `VideosStore` en filas con los nombres de columna de las tablas `venta` y
`video` del panel.

Desde la etapa 2 el panel tambien escribe: las marcas de "Publicado" van a la tabla
`publicacao`, y `traer_marcas` las baja a `grabados.db` antes de subir los videos.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import requests

from .grabados_store import VideoProducido, VideosStore
from .shopee_resolver import _graphql_call

logger = logging.getLogger(__name__)

_DIAS = 90               # lo maximo que devuelve conversionReport
_POR_PAGINA = 500        # techo de la API
_PAUSA = 1.5             # segundos entre paginas: la API tiene rate limit (10030)
_LOTE = 500              # filas por POST a Supabase
_CLAVE_VENTA = "cuenta,conversion_id,order_id,item_id,model_id"
_CLAVE_VIDEO = "canal,item_id"

_CAMPOS = (
    "nodes{clickTime purchaseTime conversionId referrer utmContent"
    " orders{orderId items{itemId modelId itemName itemPrice qty itemTotalCommission"
    " displayItemStatus completeTime imageUrl categoryLv1Name}}}"
    " pageInfo{hasNextPage scrollId}"
)

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
    """Una fila de `video` por cada (canal, producto) de `grabados.db`. Un canal que
    no esta en CUENTA_DE_CANAL se saltea: `sincronizar` lo informa como error."""
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
        if v.canal in CUENTA_DE_CANAL
    ]


def _sin_repetidas(filas: list[dict], clave: str) -> list[dict]:
    """Postgres rechaza un upsert que toca la misma fila dos veces en un lote
    ("ON CONFLICT DO UPDATE command cannot affect row a second time"). Gana la
    ultima aparicion."""
    columnas = clave.split(",")
    unicas = {tuple(f[c] for c in columnas): f for f in filas}
    return list(unicas.values())


def leer_conversiones(
    app_id: str,
    secret: str,
    *,
    desde: int,
    hasta: int,
    http_post: Callable[..., object] | None = None,
    pausa: float = _PAUSA,
) -> tuple[list[dict], str | None]:
    """Todos los nodos de `conversionReport` entre `desde` y `hasta` (epoch), pagina
    por pagina. Si una pagina falla devuelve lo leido hasta ahi y el error: lo
    leido sirve igual (el upsert es idempotente), pero la corrida no fue completa."""
    kwargs: dict[str, Any] = {"http_post": http_post} if http_post is not None else {}
    nodos: list[dict] = []
    scroll: str | None = None
    pagina = 1
    while True:
        args = f"purchaseTimeStart:{desde},purchaseTimeEnd:{hasta},limit:{_POR_PAGINA}"
        if scroll:
            args += f',scrollId:"{scroll}"'
        data = _graphql_call(app_id, secret, f"{{conversionReport({args}){{{_CAMPOS}}}}}",
                             **kwargs)
        if data is None:
            return nodos, f"La API de Shopee no respondio (pagina {pagina})"
        reporte = data.get("conversionReport") or {}
        nodos.extend(reporte.get("nodes") or [])
        info = reporte.get("pageInfo") or {}
        if not info.get("hasNextPage") or not info.get("scrollId"):
            return nodos, None
        scroll = info["scrollId"]
        pagina += 1
        time.sleep(pausa)


def _sin_error(r: Any, ruta: str) -> None:
    if r.status_code >= 300:
        raise RuntimeError(f"Supabase respondio {r.status_code} en {ruta.split('?')[0]}: "
                           f"{(r.text or '')[:300]}")


class Supabase:
    """Escritura en el panel por PostgREST, con la llave de servicio (salta RLS).
    Esa llave nunca aparece en un error ni en el log."""

    def __init__(self, url: str, llave: str, *, http: Any = requests) -> None:
        self._url = url.rstrip("/")
        self._headers = {"apikey": llave, "Authorization": f"Bearer {llave}",
                         "Content-Type": "application/json"}
        self._http = http

    def _post(self, ruta: str, cuerpo: Any, prefer: str) -> None:
        r = self._http.post(f"{self._url}/rest/v1/{ruta}", json=cuerpo,
                            headers={**self._headers, "Prefer": prefer}, timeout=60)
        _sin_error(r, ruta)

    def borrar(self, tabla: str, **filtros: Any) -> None:
        condiciones = "&".join(f"{k}=eq.{v}" for k, v in filtros.items())
        r = self._http.delete(f"{self._url}/rest/v1/{tabla}?{condiciones}",
                              headers={**self._headers, "Prefer": "return=minimal"}, timeout=60)
        _sin_error(r, tabla)

    def leer(self, tabla: str, columnas: str) -> list[dict]:
        r = self._http.get(f"{self._url}/rest/v1/{tabla}?select={columnas}",
                           headers=self._headers, timeout=60)
        _sin_error(r, tabla)
        return r.json()

    def upsert(self, tabla: str, filas: list[dict], conflicto: str) -> None:
        for i in range(0, len(filas), _LOTE):
            self._post(f"{tabla}?on_conflict={conflicto}", filas[i:i + _LOTE],
                       "resolution=merge-duplicates,return=minimal")

    def registrar(self, cuenta: str | None, empezo: datetime, ok: bool, filas: int,
                  error: str | None) -> None:
        self._post("sincronizacion", {
            "cuenta": cuenta, "empezo": empezo.isoformat(),
            "termino": datetime.now(UTC).isoformat(), "ok": ok, "filas": filas,
            "error": error,
        }, "return=minimal")


def _registrar(db: Any, cuenta: str | None, empezo: datetime, ok: bool, filas: int,
               error: str | None) -> None:
    # Si ni siquiera se puede anotar la corrida, se loguea y se sigue: no tiene que
    # frenar a la otra cuenta.
    try:
        db.registrar(cuenta, empezo, ok, filas, error)
    except Exception as exc:  # noqa: BLE001
        logger.error("No pude registrar la corrida de %s: %s", cuenta or "videos", exc)


def traer_marcas(db: Any, store: VideosStore) -> tuple[int, list[tuple[str, int]], str | None]:
    """Baja a `grabados.db` los videos marcados como publicados desde el panel.
    Nunca pisa una fecha ya puesta. Devuelve (cuantos marco, consumidas, error).

    Consumidas = marcas cuyo video ya quedo publicado en esta PC: `sincronizar` las
    borra del panel despues de subir los videos, asi una marca deshecha por el chat
    no revive en la corrida siguiente. Un video que no existe en esta PC se loguea y
    no se consume. Ningun error de aca frena la corrida: se devuelve."""
    marcadas = 0
    consumidas: list[tuple[str, int]] = []
    try:
        marcas = db.leer("publicacao", "canal,item_id,publicado_en")
        for m in marcas:
            item_id, canal = int(m["item_id"]), m["canal"]
            if not store.ya_tiene_video(item_id, canal):
                logger.warning("Marca del panel para un video que no esta en la PC: %s/%s",
                               canal, item_id)
                continue
            cuando = datetime.fromisoformat(m["publicado_en"]).timestamp()
            if store.marcar_si_falta(item_id, canal, cuando=cuando):
                marcadas += 1
            consumidas.append((canal, item_id))
    except Exception as exc:  # noqa: BLE001
        return marcadas, consumidas, f"No pude traer las marcas del panel: {exc}"
    return marcadas, consumidas, None


def sincronizar(
    cuentas: dict[str, tuple[str, str]],
    videos: list[VideoProducido],
    db: Any,
    *,
    ahora: datetime,
    http_post: Callable[..., object] | None = None,
    pausa: float = _PAUSA,
    error_marcas: str | None = None,
    marcas_consumidas: list[tuple[str, int]] = (),
) -> dict[str, bool]:
    """Una corrida completa. `cuentas` = {cuenta: (app_id, secret)}. Se releen los
    90 dias enteros cada vez porque una venta puede seguir pendiente semanas: leer
    solo lo nuevo perderia el paso a completada o cancelada. Una cuenta que falla
    no frena a la otra. Devuelve si salio bien cada cuenta y los videos."""
    fin = int(ahora.timestamp())
    resultado: dict[str, bool] = {}
    for cuenta, (app_id, secret) in cuentas.items():
        empezo = datetime.now(UTC)
        nodos, error = leer_conversiones(app_id, secret, desde=fin - _DIAS * 86400,
                                         hasta=fin, http_post=http_post, pausa=pausa)
        filas = _sin_repetidas(filas_de_ventas(cuenta, nodos, vista_en=ahora), _CLAVE_VENTA)
        escritas = 0
        try:
            db.upsert("venta", filas, _CLAVE_VENTA)
            escritas = len(filas)
        except Exception as exc:  # noqa: BLE001
            error = f"{error}; {exc}" if error else str(exc)
        resultado[cuenta] = error is None
        _registrar(db, cuenta, empezo, error is None, escritas, error)

    empezo = datetime.now(UTC)
    desconocidos = sorted({v.canal for v in videos if v.canal not in CUENTA_DE_CANAL})
    aviso = f"Canales sin cuenta en el panel: {', '.join(desconocidos)}" if desconocidos else None
    if error_marcas:
        aviso = f"{aviso}; {error_marcas}" if aviso else error_marcas
    try:
        filas_v = _sin_repetidas(filas_de_videos(videos), _CLAVE_VIDEO)
        db.upsert("video", filas_v, _CLAVE_VIDEO)
        # Recien con el video arriba (y su `publicado_en`) la marca ya no hace falta.
        for canal, item_id in marcas_consumidas:
            db.borrar("publicacao", canal=canal, item_id=item_id)
        resultado["videos"] = aviso is None
        _registrar(db, None, empezo, aviso is None, len(filas_v), aviso)
    except Exception as exc:  # noqa: BLE001
        resultado["videos"] = False
        _registrar(db, None, empezo, False, 0, f"{aviso}; {exc}" if aviso else str(exc))
    return resultado
