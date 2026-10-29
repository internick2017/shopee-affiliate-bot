"""Registrar un video producido con el link de afiliado de SU canal.

Regla de Nick (2026-10-13): ninguna publicacion sale sin el link de afiliado de la
cuenta correcta. Nick y Lanny son cuentas de afiliado distintas, y el gotcha mas
caro de shopee-video-flow fue un video del canal de uno con el link del otro: la
comision se va a la cuenta equivocada y no se ve mirando el video.

Desde aca no hay forma de saber de que cuenta es un shortlink ya hecho
(`generateShortLink` devuelve uno nuevo en cada llamada, incluso con las
credenciales de la cuenta duena). Lo que SI se puede es no aceptar links de
afuera: `registrar_video` busca la URL del producto y genera el shortlink con las
credenciales del canal, en el momento de registrar. El `link_propio` del offer
del Paso 1 no se usa para esto.

Los subIds del link son [<plataforma>, <canal>], para que el panel de Shopee separe
las ventas por donde nacen: "video" es Shopee Video (el default), "youtube" el canal
de YouTube, y asi con cada red.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping

from .grabados_store import VideosStore
from .shopee_resolver import ShopeeOffer, _graphql_call, retag_shopee_url

# Por canal, de donde salen las credenciales de SU cuenta de afiliado.
CUENTAS: dict[str, tuple[str, str]] = {
    "lanny": ("SHOPEE_APP_ID", "SHOPEE_SECRET"),
    "nick": ("SHOPEE_APP_ID_NICK", "SHOPEE_SECRET_NICK"),
}


def credenciales(canal: str, env: Mapping[str, str | None] | None = None) -> tuple[str, str]:
    """(app_id, secret) de la cuenta de afiliado del canal. ValueError si falta algo,
    nombrando la variable, para que el error diga que hay que cargar en el .env."""
    if canal not in CUENTAS:
        raise ValueError(f"Canal desconocido: {canal!r} (conocidos: {sorted(CUENTAS)})")
    env = os.environ if env is None else env
    var_app, var_sec = CUENTAS[canal]
    app_id, secret = env.get(var_app), env.get(var_sec)
    if not app_id or not secret:
        raise ValueError(f"Faltan {var_app} / {var_sec} en el .env del bot para el canal {canal}")
    return app_id, secret


def _url_del_producto(item_id: int, app_id: str, secret: str) -> str | None:
    """URL larga del producto segun la Affiliate Open API (el shortlink de tracking
    no sirve para re-taguear)."""
    query = f"query {{ productOfferV2(itemId: {item_id}, limit: 1) {{ nodes {{ itemId productLink }} }} }}"
    data = _graphql_call(app_id, secret, query)
    nodos = ((data or {}).get("productOfferV2") or {}).get("nodes") or []
    if not nodos or int(nodos[0].get("itemId") or 0) != item_id:
        return None
    return nodos[0].get("productLink") or None


def link_del_canal(
    item_id: int,
    canal: str,
    *,
    plataforma: str = "video",
    env: Mapping[str, str | None] | None = None,
    buscar_url: Callable[[int, str, str], str | None] = _url_del_producto,
    retag: Callable[[str, str, str, list[str]], str | None] = retag_shopee_url,
) -> str:
    """Shortlink de afiliado del producto, generado con las credenciales del canal.
    RuntimeError si Shopee no devuelve el producto o no da el link: mejor cortar
    que registrar un video sin link o con el link de otra cuenta."""
    app_id, secret = credenciales(canal, env)
    url = buscar_url(item_id, app_id, secret)
    if not url:
        raise RuntimeError(f"Shopee no devuelve el producto {item_id} para la cuenta de {canal}")
    link = retag(url, app_id, secret, [plataforma, canal])
    if not link:
        raise RuntimeError(f"No pude generar el link de afiliado de {canal} para el producto {item_id}")
    return link


def registrar_video(
    store: VideosStore,
    of: ShopeeOffer,
    *,
    canal: str,
    herramienta: str,
    marca: str,
    archivo: str,
    legenda: str | None = None,
    env: Mapping[str, str | None] | None = None,
    buscar_url: Callable[[int, str, str], str | None] = _url_del_producto,
    retag: Callable[[str, str, str, list[str]], str | None] = retag_shopee_url,
) -> str:
    """Paso 8.5 de shopee-video-flow: registra el video en `videos_producidos` con
    un link generado por la cuenta del canal. Devuelve ese link. No acepta un link
    de afuera a proposito. Si el link no se puede generar, no registra nada."""
    if of.item_id is None:
        raise ValueError("El offer no tiene item_id: sin eso no hay producto que registrar")
    link = link_del_canal(of.item_id, canal, env=env, buscar_url=buscar_url, retag=retag)
    store.registrar(
        of.item_id,
        canal=canal,
        titulo=of.titulo,
        link=link,
        precio=float(of.precio),
        comision_pct=float(of.comision_pct),
        herramienta=herramienta,
        marca=marca,
        archivo=archivo,
        legenda=legenda,
    )
    return link
