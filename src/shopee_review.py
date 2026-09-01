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
from decimal import Decimal

from .links import SHOPEE_LINK_RE
from .models import Product
from .post_builder import build_post, rango_relevante
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


class _Descartado:
    """Sentinel: la oferta se descartó a propósito (comisión insuficiente) — el
    caller NO debe caer al reenvío marcado, a diferencia de un `None` normal
    (que sí cae, por ambigüedad o por no poder resolver el link)."""


DESCARTADO_POR_COMISION = _Descartado()


def has_shopee_links(text: str | None) -> bool:
    """True si el texto contiene al menos un link de Shopee."""
    return has_links(text, _SHOPEE_RE)


def build_shopee_review_message(text: str | None, marker: str = DEFAULT_MARKER) -> str | None:
    """Si hay link de Shopee, arma el mensaje a revisar: marca + texto (sin footer del
    competidor ni los productos de otras plataformas). None si no hay Shopee."""
    return build_review_message(text, _SHOPEE_RE, marker, platform=PLATFORM)


def shopee_dedup_key(text: str | None) -> str | None:
    """Clave estable para deduplicar una oferta de Shopee (Shopee no expone un id
    de producto en el shortlink, así que se usan los links mismos)."""
    return review_dedup_key(text, _SHOPEE_RE, PLATFORM)


def _build_post_propio(offer: ShopeeOffer, extra_link: str | None, hook: str) -> str:
    """El post con el template de Lanny y los datos que Shopee informa AHORA."""
    # Sin descuento no se escribe la línea: "0% OFF" anuncia una oferta que no
    # existe. Solo llega acá cuando el usuario pidió publicarlo igual desde el bot
    # generador; el pipeline automático sigue exigiendo descuento antes de llamar.
    extras: list[str] = []
    if offer.descuento_pct > 0:
        extras.append(f"🏷️ {offer.descuento_pct}% OFF")
    if extra_link:
        extras.append(f"🎟️ Ative o cupom aqui: {extra_link}")

    producto = Product(
        item_id=0,
        shop_id=0,
        name=offer.titulo,
        price_final=offer.precio,
        image_url=offer.imagen_url or "",
        price_original=offer.precio_previo,
        affiliate_link=offer.link_propio,
        # Con variaciones caras el post dice "A partir de": el precio de Shopee es
        # el de la variacion mas barata (medido: 300 de 300), y anunciarlo como
        # "Por:" es una promesa que el carrito no cumple.
        is_price_range=rango_relevante(offer.precio_min, offer.precio_max),
    )
    return build_post(producto, hook, extra_lines=tuple(extras))


def build_shopee_auto_post(
    text: str | None,
    app_id: str,
    secret: str,
    *,
    hook: str | None = None,
    umbral_comision: Decimal = Decimal("6"),
    http_get: Callable[..., object] | None = None,
    http_post: Callable[..., object] | None = None,
) -> str | _Descartado | None:
    """Arma el post YA MONETIZADO de Shopee con datos reales de la Affiliate Open API.

    Sin `hook`, o si el mensaje no tiene exactamente un shortlink que resuelva a un
    producto con descuento comprobable, devuelve None — el caller cae al reenvío
    marcado. Si el ÚNICO link del mensaje resuelve a un producto con descuento real
    pero comisión por debajo de `umbral_comision`, devuelve el sentinel
    DESCARTADO_POR_COMISION en cambio — el caller NO debe caer al reenvío marcado en
    ese caso (decisión explícita: si no es del rubro, no se muestra ni una vez).
    Nunca hay un "camino viejo": esta función es enteramente nueva, Shopee nunca tuvo
    auto-post antes de esto.
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
    ofertas_bajo_umbral: list[ShopeeOffer] = []
    no_producto: list[str] = []

    for link in enlaces:
        offer = resolve_shopee_offer(link, app_id, secret, **resolve_kwargs)
        if offer and offer.tiene_descuento:
            if offer.comision_pct >= umbral_comision:
                ofertas_resueltas.append(offer)
            else:
                ofertas_bajo_umbral.append(offer)
        else:
            # o no tiene forma de producto, o productOfferV2 no tuvo datos, o sí
            # resolvió pero sin descuento activo (priceDiscountRate 0) — en
            # cualquier caso, no cuenta como producto confirmado Y no se sabe si
            # es "extra" sin re-resolver la URL — se hace una vez más, liviano
            # (ya se pagó el costo del redirect adentro de resolve_shopee_offer,
            # pero acá hace falta la URL resuelta para clasificar, así que se
            # repite el get). Ver Task 3 nota de diseño. IMPORTANTE: esta rama
            # tiene que capturar TODO lo que no entró en ofertas_resueltas ni en
            # ofertas_bajo_umbral, para que el chequeo de "un único link en el
            # mensaje" de la línea de abajo (DESCARTADO_POR_COMISION) sea
            # confiable — un link "perdido" ahí rompería esa cuenta (bug real
            # encontrado en review, 2026-07-19).
            no_producto.append(link)

    if len(ofertas_resueltas) != 1:
        # caso simple y sin ambigüedad: un único link, resolvió a un producto con
        # descuento real, y la única razón por la que no cuenta es la comisión baja
        # -> descarte a propósito, no ambigüedad. Cualquier otra combinación (cero
        # ofertas, más de una, o hay links no-producto de por medio) sigue cayendo
        # al reenvío marcado de siempre, igual que antes de este feature.
        if not ofertas_resueltas and len(ofertas_bajo_umbral) == 1 and not no_producto:
            return DESCARTADO_POR_COMISION
        return None
    offer = ofertas_resueltas[0]

    extra_link = None
    for link in no_producto:
        from .shopee_resolver import _default_get, _resolve_redirect

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
        umbral_comision: Decimal = Decimal("6"),
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
        self._umbral_comision = umbral_comision

    async def handle(self, text, chat_title=None, photo=None) -> int:
        if self._app_id and self._secret and has_shopee_links(text):
            auto_msg = await asyncio.to_thread(
                build_shopee_auto_post,
                text,
                self._app_id,
                self._secret,
                hook=self._hooks.next() if self._hooks else None,
                umbral_comision=self._umbral_comision,
            )
            if auto_msg is DESCARTADO_POR_COMISION:
                logger.info(
                    "Oferta de Shopee descartada por comisión baja (< %s%%)",
                    self._umbral_comision,
                )
                return 0
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
