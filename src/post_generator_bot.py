"""Lógica pura del bot generador de posts: dado el texto que un usuario mandó por
Telegram, arma la respuesta (foto + caption) o el mensaje de error. No importa nada
de la librería de Telegram — eso vive en `bot_generador.py`, que es un wrapper fino
alrededor de `generate_post_reply`.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace

from .post_builder import HookBank
from .shopee_resolver import extract_shopee_shortlinks, resolve_shopee_offer
from .shopee_review import _build_post_propio
from .vertical_canvas import build_vertical_canvas

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
    user_credentials: tuple[str, str] | None = None,
    http_get: Callable[..., object] | None = None,
    http_post: Callable[..., object] | None = None,
) -> BotReply:
    """Toma UN link de Shopee del texto (el primero, si hay varios) y arma el post.

    Solo usa el primer link: el bot está pensado para "un link, un post", a
    diferencia del pipeline automático que maneja mensajes de fuentes con varios
    links (producto + cupón) — acá el usuario manda un link a la vez.

    `user_credentials`: si el usuario registró su propia cuenta de Shopee Affiliate
    (`app_id`, `secret`), se usa para resolver, y el post lleva SU link propio. Sin
    registrar, `app_id`/`secret` (la cuenta por defecto) solo se usan para leer los
    datos del producto — el post lleva el link tal cual lo mandó el usuario, no el
    de la cuenta por defecto (retaguearlo sería monetizar para la cuenta equivocada).
    """
    links = extract_shopee_shortlinks(text)
    if not links:
        return BotReply(error=_ERROR_SIN_LINK)
    link_original = links[0]

    resolve_kwargs = {}
    if http_get is not None:
        resolve_kwargs["http_get"] = http_get
    if http_post is not None:
        resolve_kwargs["http_post"] = http_post

    resolve_app_id, resolve_secret = user_credentials or (app_id, secret)
    offer = resolve_shopee_offer(link_original, resolve_app_id, resolve_secret, **resolve_kwargs)
    if offer is None or not offer.tiene_descuento:
        return BotReply(error=_ERROR_NO_RESUELVE)

    if user_credentials is None:
        offer = replace(offer, link_propio=link_original)

    caption = _build_post_propio(offer, None, hooks.next())
    return BotReply(caption=caption, photo_url=offer.imagen_url)


_ERROR_SIN_FOTO = (
    "Pude leer el producto pero no conseguí bajar la foto de Shopee. Probá de nuevo en un rato."
)

# Prompt para el generador de video. La imagen que lo acompaña YA es 9:16, así que
# no hay que pelear por el formato — el error clásico era pedir 9:16 por texto con
# una imagen cuadrada, y ahí el modelo rellenaba el alto faltante inventando un
# mockup de celular. Acá solo se pide animar lo que ya está encuadrado.
_PROMPT_VIDEO = """Anime esta imagem de referência em um vídeo publicitário de 10 segundos.

Mantenha EXATAMENTE o mesmo enquadramento vertical da imagem, preenchendo todo o quadro.
O produto deve permanecer idêntico: mesmo formato, cores, materiais, proporções e detalhes.

0-3s: o produto em destaque.
3-7s: o produto em uso ou seus detalhes principais.
7-10s: enquadramento final claro do produto.

Movimentos suaves de câmera e zoom leve. Fotorrealista, iluminação profissional.

NÃO mostre telefone, moldura, tela ou interface de aplicativo.
NÃO adicione texto, logotipos, pessoas, animais nem objetos novos.
NÃO mostre crianças ou bebês."""


@dataclass
class VideoReference:
    """Imagen 9:16 lista para un generador de video, más el prompt sugerido.
    `error` presente = el resto ausente, igual que `BotReply`."""

    image_bytes: bytes | None = None
    caption: str | None = None
    filename: str | None = None
    error: str | None = None


def generate_video_reference(
    text: str,
    app_id: str,
    secret: str,
    *,
    user_credentials: tuple[str, str] | None = None,
    http_get: Callable[..., object] | None = None,
    http_post: Callable[..., object] | None = None,
    fetch_image: Callable[[str], bytes] | None = None,
) -> VideoReference:
    """Resuelve el link de Shopee, baja la foto del producto y devuelve el lienzo
    vertical 1080x1920 con el prompt de video.

    `fetch_image` se inyecta para los tests; por defecto baja con `requests`."""
    links = extract_shopee_shortlinks(text)
    if not links:
        return VideoReference(error=_ERROR_SIN_LINK)

    resolve_kwargs = {}
    if http_get is not None:
        resolve_kwargs["http_get"] = http_get
    if http_post is not None:
        resolve_kwargs["http_post"] = http_post

    resolve_app_id, resolve_secret = user_credentials or (app_id, secret)
    offer = resolve_shopee_offer(links[0], resolve_app_id, resolve_secret, **resolve_kwargs)
    if offer is None:
        return VideoReference(error=_ERROR_NO_RESUELVE)
    if not offer.imagen_url:
        return VideoReference(error=_ERROR_SIN_FOTO)

    try:
        raw = (fetch_image or _bajar_imagen)(offer.imagen_url)
    except Exception:
        return VideoReference(error=_ERROR_SIN_FOTO)
    if not raw:
        return VideoReference(error=_ERROR_SIN_FOTO)

    return VideoReference(
        image_bytes=build_vertical_canvas(raw),
        caption=f"{offer.titulo}\n\n{_PROMPT_VIDEO}",
        filename="referencia-9x16.jpg",
    )


def _bajar_imagen(url: str) -> bytes:
    import requests

    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.content
