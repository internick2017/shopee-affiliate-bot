"""Núcleo compartido de los handlers de "reenviar a revisar".

Shopee y Mercado Livre no se pueden monetizar automáticamente: Shopee exige generar
el link en su panel, y Mercado Livre esconde el producto dentro de un `ref` cifrado
(`/social/<afiliado>?ref=...`). En ambos casos el bot reenvía la oferta marcada al
canal de esa plataforma y el owner arma el link a mano.

La lógica es la misma para las dos, así que vive acá una sola vez: lo único que
cambia es qué links detectar, con qué marca y con qué prefijo de dedup.
"""
import logging
import re
from typing import Optional

from .posting import post_offer

logger = logging.getLogger(__name__)

# Footer del competidor: mismos marcadores que usa amazon_retagger.
FOOTER_MARKERS = ("grupos de promos", "ctlinks.com.br")


def has_links(text: Optional[str], link_re: re.Pattern) -> bool:
    if not text:
        return False
    return bool(link_re.search(text))


def build_review_message(
    text: Optional[str], link_re: re.Pattern, marker: str
) -> Optional[str]:
    """Marca + texto original sin el footer del competidor. None si no hay links."""
    if not has_links(text, link_re):
        return None
    filtered = [
        line
        for line in text.split("\n")
        if not any(m in line.lower() for m in FOOTER_MARKERS)
    ]
    cleaned = "\n".join(filtered).strip("\n")
    return f"{marker}\n\n{cleaned}"


def review_dedup_key(
    text: Optional[str], link_re: re.Pattern, prefix: str
) -> Optional[str]:
    """Clave de dedup a partir de los links, sin query params (`?lp=aff` cambia
    según quién postee) y ordenados (el orden en el mensaje no significa nada).

    Ojo: distintos canales acortan el mismo producto con tokens distintos, así que
    esto deduplica repeticiones dentro de un canal, no entre canales.
    """
    links = link_re.findall(text or "")
    if not links:
        return None
    normalized = sorted({link.split("?")[0].rstrip("/") for link in links})
    return f"{prefix}:" + "|".join(normalized)


class ReviewPipeline:
    """Handler que reenvía las ofertas de una plataforma al canal para monetizar a mano.

    Misma interfaz que AmazonPipeline: handle(text, chat_title) -> int (0 = no la manejó).
    """

    def __init__(self, poster, *, link_re, marker, prefix, platform, dedup=None):
        self._poster = poster
        self._link_re = link_re
        self._marker = marker
        self._prefix = prefix
        self._platform = platform
        self._dedup = dedup

    def dedup_key(self, text) -> Optional[str]:
        return review_dedup_key(text, self._link_re, self._prefix)

    async def handle(self, text, chat_title=None, photo=None) -> int:
        key = self.dedup_key(text)
        if key and self._dedup and self._dedup.seen(key):
            logger.info("Oferta de %s ya reenviada (%s); se omite", self._platform, key)
            return 1

        msg = build_review_message(text, self._link_re, self._marker)
        if not msg:
            return 0
        await post_offer(self._poster, msg, photo)
        if key and self._dedup:
            self._dedup.mark(key)
        logger.info("Oferta de %s reenviada al canal para revisar", self._platform)
        return 1
