"""Handler de Mercado Livre: si el link `meli.la` resuelve a un producto puntual,
arma el post con el link propio de Nick (automático). Si no, reenvía la oferta al
canal para armar el link a mano.

Los tres canales fuente postean shortlinks `meli.la/XXXX` que redirigen a
`mercadolivre.com.br/social/<afiliado>?ref=<blob>`: el `ref` va cifrado y firmado a
la cuenta que lo generó, así que no se puede reescribir. Pero la página resuelta
trae embebido el item_id real del producto (ver `mercadolivre_resolver.py`), y con
eso alcanza para armar el link propio sin pasar por la Central de Afiliados. Cuando
el link es de tipo "lista" (sin item_id resoluble), no hay nada que automatizar: se
sigue reenviando marcado para que Nick lo genere a mano.
"""
import asyncio
import logging
from collections.abc import Callable

from .links import MERCADOLIVRE_LINK_RE, foreign_link_res
from .mercadolivre_resolver import build_own_mercadolivre_links
from .posting import post_offer
from .review_forward import (
    FOOTER_MARKERS,
    ReviewPipeline,
    build_review_message,
    drop_foreign_blocks,
    has_links,
    review_dedup_key,
)

logger = logging.getLogger(__name__)

_MERCADOLIVRE_RE = MERCADOLIVRE_LINK_RE
PLATFORM = "ml"

DEFAULT_MARKER = "⚠️ MERCADO LIVRE: gerar link de afiliado e postar manual"


def has_mercadolivre_links(text: str | None) -> bool:
    """True si el texto contiene al menos un link de Mercado Livre."""
    return has_links(text, _MERCADOLIVRE_RE)


def build_mercadolivre_review_message(
    text: str | None, marker: str = DEFAULT_MARKER
) -> str | None:
    """Marca + texto original sin el footer del competidor ni los productos de otras
    plataformas. None si no hay ML."""
    return build_review_message(text, _MERCADOLIVRE_RE, marker, platform=PLATFORM)


def mercadolivre_dedup_key(text: str | None) -> str | None:
    return review_dedup_key(text, _MERCADOLIVRE_RE, PLATFORM)


def build_mercadolivre_auto_post(
    text: str | None,
    matt_word: str,
    matt_tool: str,
    *,
    http_get: Callable[..., object] | None = None,
) -> str | None:
    """Arma el post YA MONETIZADO reemplazando cada shortlink meli.la por el link
    propio de Nick. None si no hay shortlinks resolubles, o si ALGUNO no resolvió
    (todo-o-nada: el caller cae al reenvío manual, sin marca en este camino).
    """
    resolve_kwargs = {} if http_get is None else {"http_get": http_get}
    resolved = build_own_mercadolivre_links(text, matt_word, matt_tool, **resolve_kwargs)
    if not resolved:
        return None

    assert text is not None
    result = text
    for shortlink, own_link in resolved.items():
        result = result.replace(shortlink, own_link)

    filtered = "\n".join(
        line
        for line in result.split("\n")
        if not any(marker in line.lower() for marker in FOOTER_MARKERS)
    )
    filtered = drop_foreign_blocks(filtered, _MERCADOLIVRE_RE, foreign_link_res(PLATFORM))
    return filtered.strip()


class MercadoLivreReviewPipeline(ReviewPipeline):
    """Intenta el post automático (ver build_mercadolivre_auto_post); si no se puede,
    cae al reenvío manual de siempre (comportamiento heredado de ReviewPipeline)."""

    def __init__(
        self,
        poster,
        marker: str = DEFAULT_MARKER,
        dedup=None,
        matt_word: str | None = None,
        matt_tool: str | None = None,
    ):
        super().__init__(
            poster,
            link_re=_MERCADOLIVRE_RE,
            marker=marker,
            prefix=PLATFORM,
            platform="Mercado Livre",
            dedup=dedup,
        )
        self._matt_word = matt_word
        self._matt_tool = matt_tool

    async def handle(self, text, chat_title=None, photo=None) -> int:
        if self._matt_word and self._matt_tool:
            auto_msg = await asyncio.to_thread(
                build_mercadolivre_auto_post, text, self._matt_word, self._matt_tool
            )
            if auto_msg:
                key = self.dedup_key(text)
                if key and self._dedup and not self._dedup.claim(key):
                    logger.info(
                        "Oferta de Mercado Livre ya publicada (%s); se omite", key
                    )
                    return 1
                try:
                    await post_offer(self._poster, auto_msg, photo)
                except Exception:
                    if key and self._dedup:
                        self._dedup.release(key)
                    raise
                logger.info("Oferta de Mercado Livre auto-monetizada y publicada")
                return 1

        return await super().handle(text, chat_title, photo=photo)
