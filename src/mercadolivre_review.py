"""Handler de Mercado Livre: reenvía la oferta al canal para armar el link a mano.

No se puede monetizar automáticamente. Los tres canales fuente postean shortlinks
`meli.la/XXXX` que redirigen a `mercadolivre.com.br/social/<afiliado>?ref=<blob>`:
el `ref` va cifrado y la página es el escaparate entero del afiliado, no un producto.
Sin id de producto (MLB) no hay URL que re-taguear, así que el owner genera el link
desde su panel de afiliado usando el nombre y el precio que vienen en el mensaje.
"""
import re
from typing import Optional

from .review_forward import (
    ReviewPipeline,
    build_review_message,
    has_links,
    review_dedup_key,
)

# meli.la (shortlink), mercadolivre.com.br y mercadolivre.com (link largo o /social/).
_MERCADOLIVRE_RE = re.compile(
    r"https?://meli\.la/\S+|https?://(?:[\w-]+\.)*mercadolivre\.com(?:\.br)?/\S+",
    re.IGNORECASE,
)

DEFAULT_MARKER = "⚠️ MERCADO LIVRE: gerar link de afiliado e postar manual"


def has_mercadolivre_links(text: Optional[str]) -> bool:
    """True si el texto contiene al menos un link de Mercado Livre."""
    return has_links(text, _MERCADOLIVRE_RE)


def build_mercadolivre_review_message(
    text: Optional[str], marker: str = DEFAULT_MARKER
) -> Optional[str]:
    """Marca + texto original sin el footer del competidor. None si no hay ML."""
    return build_review_message(text, _MERCADOLIVRE_RE, marker)


def mercadolivre_dedup_key(text: Optional[str]) -> Optional[str]:
    return review_dedup_key(text, _MERCADOLIVRE_RE, "ml")


class MercadoLivreReviewPipeline(ReviewPipeline):
    def __init__(self, poster, marker: str = DEFAULT_MARKER, dedup=None):
        super().__init__(
            poster,
            link_re=_MERCADOLIVRE_RE,
            marker=marker,
            prefix="ml",
            platform="Mercado Livre",
            dedup=dedup,
        )
