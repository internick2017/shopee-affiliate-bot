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

from .links import foreign_link_res, has_any_link
from .posting import post_offer

logger = logging.getLogger(__name__)

# Footer del competidor: mismos marcadores que usa amazon_retagger.
FOOTER_MARKERS = ("grupos de promos", "ctlinks.com.br")


def has_links(text: str | None, link_re: re.Pattern) -> bool:
    if not text:
        return False
    return bool(link_re.search(text))


def _split_blocks(text: str) -> list[str]:
    """Parte el mensaje en bloques separados por líneas en blanco. Las fuentes postean
    un bloque por producto (nombre, precio, link)."""
    blocks: list[str] = []
    current: list[str] = []
    for line in text.split("\n"):
        if line.strip():
            current.append(line)
        elif current:
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    return blocks


def drop_foreign_blocks(
    text: str, link_re: re.Pattern, foreign_res: tuple[re.Pattern, ...]
) -> str:
    """Quita los bloques cuyo único link es de otra plataforma.

    Un mensaje de Crowman trae Amazon y Mercado Livre mezclados. Sin esto, el canal de
    ML recibiría también los productos de Amazon —ya publicados y monetizados en su
    propio canal— con el tag de afiliado del competidor intacto.

    Un bloque sin links (un encabezado) se conserva: no es de nadie y da contexto.
    Un mensaje sin líneas en blanco es un solo bloque y sobrevive entero.
    """
    if not foreign_res:
        return text
    kept = [
        block
        for block in _split_blocks(text)
        if link_re.search(block) or not has_any_link(block, foreign_res)
    ]
    return "\n\n".join(kept)


def build_review_message(
    text: str | None,
    link_re: re.Pattern,
    marker: str,
    *,
    platform: str | None = None,
) -> str | None:
    """Marca + texto original sin el footer del competidor. None si no hay links.

    Con `platform` (la clave en `links.PLATFORM_LINK_RES`) también descarta los
    bloques de las otras plataformas.
    """
    if not has_links(text, link_re):
        return None
    assert text is not None
    filtered = "\n".join(
        line
        for line in text.split("\n")
        if not any(m in line.lower() for m in FOOTER_MARKERS)
    )
    filtered = drop_foreign_blocks(filtered, link_re, foreign_link_res(platform))
    return f"{marker}\n\n{filtered.strip()}"


def review_dedup_key(
    text: str | None, link_re: re.Pattern, prefix: str
) -> str | None:
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

    def dedup_key(self, text) -> str | None:
        return review_dedup_key(text, self._link_re, self._prefix)

    async def handle(self, text, chat_title=None, photo=None) -> int:
        msg = build_review_message(
            text, self._link_re, self._marker, platform=self._prefix
        )
        if not msg:
            return 0

        # `claim` reserva la clave de forma atómica: dos mensajes con la misma oferta
        # procesados a la vez no pueden ganarla los dos, así que no se reenvía repetida.
        key = self.dedup_key(text)
        if key and self._dedup and not self._dedup.claim(key):
            logger.info("Oferta de %s ya reenviada (%s); se omite", self._platform, key)
            return 1

        try:
            await post_offer(self._poster, msg, photo)
        except Exception:
            # No se publicó: liberar la clave para reintentarla en el próximo mensaje.
            if key and self._dedup:
                self._dedup.release(key)
            raise

        logger.info("Oferta de %s reenviada al canal para revisar", self._platform)
        return 1
