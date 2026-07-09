
from .links import SHOPEE_LINK_RE
from .review_forward import (
    ReviewPipeline,
    build_review_message,
    has_links,
    review_dedup_key,
)

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


class ShopeeReviewPipeline(ReviewPipeline):
    """Reenvía las ofertas de Shopee al canal para monetizar a mano: el link de
    afiliado se genera en el panel de Shopee, no se puede re-taguear por URL."""

    def __init__(self, poster, marker: str = DEFAULT_MARKER, dedup=None):
        super().__init__(
            poster,
            link_re=_SHOPEE_RE,
            marker=marker,
            prefix=PLATFORM,
            platform="Shopee",
            dedup=dedup,
        )
