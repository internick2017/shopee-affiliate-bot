import logging
from typing import Optional

from .amazon_retagger import extract_amazon_links, extract_asin
from .lanny_post import build_lanny_amazon_post

logger = logging.getLogger(__name__)


def amazon_dedup_key(text: Optional[str]) -> Optional[str]:
    """Clave estable para deduplicar una oferta de Amazon entre grupos.

    Preferimos el ASIN: el mismo producto llega de Crowman y de IAchados con
    query params y tags distintos, pero el ASIN es el mismo. Si el link no
    apunta a un producto, caemos a la URL sin query (mejor que nada).
    """
    links = extract_amazon_links(text)
    if not links:
        return None
    asin = extract_asin(links[0])
    if asin:
        return f"amazon:{asin}"
    return "amazon:" + links[0].split("?")[0]


class AmazonPipeline:
    """Turns a promo message into a Lanny-style Amazon post and publishes it."""

    def __init__(self, tag, poster, hookbank, dedup=None):
        self._tag = tag
        self._poster = poster
        self._hookbank = hookbank
        self._dedup = dedup

    async def handle(self, text, chat_title=None) -> int:
        # La clave se calcula ANTES de armar el post: `hookbank.next()` consume un
        # gancho, y un duplicado no debe gastarlo.
        key = amazon_dedup_key(text)
        if key and self._dedup and self._dedup.seen(key):
            # Devuelve 1 (=lo manejé) a propósito: el mensaje es nuestro y ya se
            # posteó. Devolver 0 lo dejaría caer al handler siguiente.
            logger.info("Oferta de Amazon ya posteada (%s); se omite", key)
            return 1

        post = build_lanny_amazon_post(text, self._tag, self._hookbank.next())
        if not post:
            return 0
        await self._poster.post_text(post)
        # Solo se marca tras postear: si el post no se pudo armar, el producto
        # sigue disponible para cuando llegue un mensaje mejor formado.
        if key and self._dedup:
            self._dedup.mark(key)
        logger.info("Post de Amazon (estilo Lanny) publicado al canal")
        return 1
