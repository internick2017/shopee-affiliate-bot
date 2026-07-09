"""Handler de Mercado Livre: reenvía la oferta al canal para armar el link a mano.

No se puede monetizar automáticamente. Los tres canales fuente postean shortlinks
`meli.la/XXXX` que redirigen a `mercadolivre.com.br/social/<afiliado>?ref=<blob>`:
el `ref` va cifrado y la página es el escaparate entero del afiliado, no un producto.
Sin id de producto (MLB) no hay URL que re-taguear, así que el owner genera el link
desde su panel de afiliado usando el nombre y el precio que vienen en el mensaje.
"""

from .links import MERCADOLIVRE_LINK_RE
from .review_forward import (
    ReviewPipeline,
    build_review_message,
    has_links,
    review_dedup_key,
)

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


class MercadoLivreReviewPipeline(ReviewPipeline):
    def __init__(self, poster, marker: str = DEFAULT_MARKER, dedup=None):
        super().__init__(
            poster,
            link_re=_MERCADOLIVRE_RE,
            marker=marker,
            prefix=PLATFORM,
            platform="Mercado Livre",
            dedup=dedup,
        )
