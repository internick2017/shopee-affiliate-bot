"""Lógica pura del bot generador de posts: dado el texto que un usuario mandó por
Telegram, arma la respuesta (foto + caption) o el mensaje de error. No importa nada
de la librería de Telegram — eso vive en `bot_generador.py`, que es un wrapper fino
alrededor de `generate_post_reply`.
"""

from collections.abc import Callable
from dataclasses import dataclass

from .post_builder import HookBank
from .shopee_resolver import extract_shopee_shortlinks, resolve_shopee_offer
from .shopee_review import _build_post_propio

_ERROR_SIN_LINK = "No encontré ningún link de Shopee en tu mensaje. Mandame el link del producto."
_ERROR_NO_RESUELVE = (
    "No pude leer ese producto en Shopee. Puede ser un link vencido, de cupón/campaña "
    "en vez de producto, o Shopee no lo tiene en su catálogo de afiliados ahora mismo."
)


@dataclass
class BotReply:
    """Lo que el bot le contesta al usuario. `error` presente = `caption`/`photo_url`
    ausentes, y viceversa — nunca los tres a la vez."""

    caption: str | None = None
    photo_url: str | None = None
    error: str | None = None


def generate_post_reply(
    text: str,
    app_id: str,
    secret: str,
    hooks: HookBank,
    *,
    http_get: Callable[..., object] | None = None,
    http_post: Callable[..., object] | None = None,
) -> BotReply:
    """Toma UN link de Shopee del texto (el primero, si hay varios) y arma el post.

    Solo usa el primer link: el bot está pensado para "un link, un post", a
    diferencia del pipeline automático que maneja mensajes de fuentes con varios
    links (producto + cupón) — acá el usuario manda un link a la vez.
    """
    links = extract_shopee_shortlinks(text)
    if not links:
        return BotReply(error=_ERROR_SIN_LINK)

    resolve_kwargs = {}
    if http_get is not None:
        resolve_kwargs["http_get"] = http_get
    if http_post is not None:
        resolve_kwargs["http_post"] = http_post

    offer = resolve_shopee_offer(links[0], app_id, secret, **resolve_kwargs)
    if offer is None or not offer.tiene_descuento:
        return BotReply(error=_ERROR_NO_RESUELVE)

    caption = _build_post_propio(offer, None, hooks.next())
    return BotReply(caption=caption, photo_url=offer.imagen_url)
