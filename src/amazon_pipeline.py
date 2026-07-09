import asyncio
import logging
from typing import Optional

from .amazon_retagger import extract_amazon_links, extract_asin
from .amazon_shortlink import expand_amazon_shortlinks, has_amazon_shortlinks
from .lanny_post import build_post_from_offer
from .offers import extract_offers
from .posting import post_offer

logger = logging.getLogger(__name__)


def offer_dedup_key(url: str) -> str:
    """Clave estable de una oferta de Amazon: el ASIN. El mismo producto llega de
    varios grupos con query params y tags de origen distintos."""
    return f"amazon:{extract_asin(url)}"


def amazon_dedup_key(text: Optional[str]) -> Optional[str]:
    """Clave de la primera oferta de Amazon del texto, o None si no hay links."""
    links = extract_amazon_links(text)
    if not links:
        return None
    asin = extract_asin(links[0])
    if asin:
        return f"amazon:{asin}"
    return "amazon:" + links[0].split("?")[0]


class AmazonPipeline:
    """Turns each Amazon offer in a promo message into a Lanny-style post."""

    def __init__(self, tag, poster, hookbank, dedup=None, expand=expand_amazon_shortlinks):
        self._tag = tag
        self._poster = poster
        self._hookbank = hookbank
        self._dedup = dedup
        self._expand = expand

    async def _expanded(self, text):
        """Resuelve los shortlinks (`link.amazon/...`) a URLs de producto.

        Solo toca la red si el mensaje trae shortlinks, y lo hace en un thread:
        `expand` bloquea en HTTP y el listener corre en este mismo event loop.
        """
        if not has_amazon_shortlinks(text):
            return text
        return await asyncio.to_thread(self._expand, text)

    async def handle(self, text, chat_title=None, photo=None) -> int:
        # Antes que nada: sin resolver, un `link.amazon/...` no matchea
        # `amazon.com.br` y el mensaje se descartaría. También hace falta para
        # conocer el ASIN, que es la clave de dedup.
        text = await self._expanded(text)

        offers = extract_offers(text)
        if not offers:
            return 0

        handled = 0
        for offer in offers:
            key = offer_dedup_key(offer.url)
            # El dedup se consulta antes de armar el post: `hookbank.next()` consume
            # un gancho, y un duplicado no debe gastarlo. Cuenta como manejado igual:
            # la oferta es nuestra, solo que ya se publicó.
            if self._dedup and self._dedup.seen(key):
                logger.info("Oferta de Amazon ya posteada (%s); se omite", key)
                handled += 1
                continue

            post = build_post_from_offer(offer, self._tag, self._hookbank.next())
            await post_offer(self._poster, post, photo)
            # Solo se marca tras postear, para que un fallo no la dé por publicada.
            if self._dedup:
                self._dedup.mark(key)
            logger.info("Post de Amazon (estilo Lanny) publicado: %s", offer.name[:60])
            handled += 1

        return handled
