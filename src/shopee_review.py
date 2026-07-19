"""Handler de Shopee: si el mensaje trae exactamente un shortlink que resuelve a un
producto con descuento comprobable, arma el post con datos reales y el link propio
(automático). Si no, reenvía la oferta al canal para armar el link a mano.

Ver `shopee_resolver.py` para el porqué de "un producto por post" y de la
clasificación de links extra (cupón/campaña vs. ruido a ignorar) — decisiones
tomadas en docs/superpowers/specs/2026-07-18-shopee-post-propio-design.md.
"""
import asyncio
import logging
from collections.abc import Callable

from .links import SHOPEE_LINK_RE
from .models import Product
from .post_builder import build_post
from .posting import post_offer
from .review_forward import ReviewPipeline, build_review_message, has_links, review_dedup_key
from .shopee_resolver import (
    ShopeeOffer,
    es_link_tipo_cupom,
    extract_shopee_shortlinks,
    resolve_shopee_offer,
    retag_shopee_url,
)

logger = logging.getLogger(__name__)

_SHOPEE_RE = SHOPEE_LINK_RE
PLATFORM = "shopee"

DEFAULT_MARKER = "⚠️ SHOPEE: gerar link de afiliado e postar manual"


def has_shopee_links(text: str | None) -> bool:
    """True si el texto contiene al menos un link de Shopee."""
    return has_links(text, _SHOPEE_RE)


def build_shopee_review_message(
    text: str | None, marker: str = DEFAULT_MARKER
) -> str | None:
    """Si hay link de Shopee, arma el mensaje a revisar: marca + texto (sin footer del
    competidor ni los productos de otras plataformas). None si no hay Shopee."""
    return build_review_message(text, _SHOPEE_RE, marker, platform=PLATFORM)


def shopee_dedup_key(text: str | None) -> str | None:
    """Clave estable para deduplicar una oferta de Shopee (Shopee no expone un id
    de producto en el shortlink, así que se usan los links mismos)."""
    return review_dedup_key(text, _SHOPEE_RE, PLATFORM)


def _build_post_propio(
    offer: ShopeeOffer, extra_link: str | None, hook: str
) -> str:
    """El post con el template de Lanny y los datos que Shopee informa AHORA."""
    extras: list[str] = [f"🏷️ {offer.descuento_pct}% OFF"]
    if extra_link:
        extras.append(f"🎟️ Ative o cupom aqui: {extra_link}")

    producto = Product(
        item_id=0,
        shop_id=0,
        name=offer.titulo,
        price_final=offer.precio,
        image_url="",
        price_original=offer.precio_previo,
        affiliate_link=offer.link_propio,
    )
    return build_post(producto, hook, extra_lines=tuple(extras))


def build_shopee_auto_post(
    text: str | None,
    app_id: str,
    secret: str,
    *,
    hook: str | None = None,
    http_get: Callable[..., object] | None = None,
    http_post: Callable[..., object] | None = None,
) -> str | None:
    """Arma el post YA MONETIZADO de Shopee con datos reales de la Affiliate Open API.

    Sin `hook`, o si el mensaje no tiene exactamente un shortlink que resuelva a un
    producto con descuento comprobable, devuelve None — el caller cae al reenvío
    marcado. Nunca hay un "camino viejo": esta función es enteramente nueva, Shopee
    nunca tuvo auto-post antes de esto.
    """
    if hook is None or not text:
        return None

    resolve_kwargs = {}
    if http_get is not None:
        resolve_kwargs["http_get"] = http_get
    if http_post is not None:
        resolve_kwargs["http_post"] = http_post

    enlaces = extract_shopee_shortlinks(text)
    if not enlaces:
        return None

    ofertas_resueltas: list[ShopeeOffer] = []
    no_producto: list[str] = []

    for link in enlaces:
        offer = resolve_shopee_offer(link, app_id, secret, **resolve_kwargs)
        if offer and offer.tiene_descuento:
            ofertas_resueltas.append(offer)
        elif offer is None:
            # o no tiene forma de producto, o productOfferV2 no tuvo datos. En
            # cualquier caso, no cuenta como producto Y no se sabe si es "extra"
            # sin re-resolver la URL — se hace una vez más, liviano (ya se pagó
            # el costo del redirect adentro de resolve_shopee_offer, pero acá
            # hace falta la URL resuelta para clasificar, así que se repite el
            # get). Ver Task 3 nota de diseño.
            no_producto.append(link)

    if len(ofertas_resueltas) != 1:
        return None
    offer = ofertas_resueltas[0]

    extra_link = None
    for link in no_producto:
        from .shopee_resolver import _resolve_redirect, _default_get

        url_resuelta = _resolve_redirect(
            link, http_get=resolve_kwargs.get("http_get", _default_get)
        )
        if url_resuelta and es_link_tipo_cupom(url_resuelta):
            subid_kwargs = {}
            if http_post is not None:
                subid_kwargs["http_post"] = http_post
            extra_link = retag_shopee_url(
                url_resuelta, app_id, secret, ["lannybot"], **subid_kwargs
            )
            break  # un solo link extra alcanza; el resto se ignora

    return _build_post_propio(offer, extra_link, hook)


class ShopeeReviewPipeline(ReviewPipeline):
    """Intenta el post automático (ver build_shopee_auto_post); si no se puede, cae
    al reenvío manual de siempre (comportamiento heredado de ReviewPipeline)."""

    def __init__(
        self,
        poster,
        marker: str = DEFAULT_MARKER,
        dedup=None,
        app_id: str | None = None,
        secret: str | None = None,
        hooks=None,
    ):
        super().__init__(
            poster,
            link_re=_SHOPEE_RE,
            marker=marker,
            prefix=PLATFORM,
            platform="Shopee",
            dedup=dedup,
        )
        self._app_id = app_id
        self._secret = secret
        self._hooks = hooks

    async def handle(self, text, chat_title=None, photo=None) -> int:
        if self._app_id and self._secret and has_shopee_links(text):
            auto_msg = await asyncio.to_thread(
                build_shopee_auto_post,
                text,
                self._app_id,
                self._secret,
                hook=self._hooks.next() if self._hooks else None,
            )
            if auto_msg:
                key = self.dedup_key(text)
                if key and self._dedup and not self._dedup.claim(key):
                    logger.info("Oferta de Shopee ya publicada (%s); se omite", key)
                    return 1
                try:
                    await post_offer(self._poster, auto_msg, photo)
                except Exception:
                    if key and self._dedup:
                        self._dedup.release(key)
                    raise
                logger.info("Oferta de Shopee auto-monetizada y publicada")
                return 1

        return await super().handle(text, chat_title, photo=photo)
