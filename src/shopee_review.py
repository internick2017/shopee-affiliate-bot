import re
from typing import Optional

from .review_forward import (
    ReviewPipeline,
    build_review_message,
    has_links,
    review_dedup_key,
)

# Detecta links de Shopee Brasil: shopee.com.br, s.shopee.com.br, shp.ee (amplio).
_SHOPEE_RE = re.compile(
    r"https?://(?:[\w-]+\.)*shopee\.com\.br/\S+|https?://shp\.ee/\S+", re.IGNORECASE
)

DEFAULT_MARKER = "⚠️ SHOPEE: gerar link de afiliado e postar manual"


def has_shopee_links(text: Optional[str]) -> bool:
    """True si el texto contiene al menos un link de Shopee."""
    return has_links(text, _SHOPEE_RE)


def build_shopee_review_message(
    text: Optional[str], marker: str = DEFAULT_MARKER
) -> Optional[str]:
    """Si hay link de Shopee, arma el mensaje a revisar: marca + texto (sin footer del
    competidor). Devuelve None si no hay Shopee."""
    return build_review_message(text, _SHOPEE_RE, marker)


def shopee_dedup_key(text: Optional[str]) -> Optional[str]:
    """Clave estable para deduplicar una oferta de Shopee (Shopee no expone un id
    de producto en el shortlink, así que se usan los links mismos)."""
    return review_dedup_key(text, _SHOPEE_RE, "shopee")


class ShopeeReviewPipeline(ReviewPipeline):
    """Reenvía las ofertas de Shopee al canal para monetizar a mano: el link de
    afiliado se genera en el panel de Shopee, no se puede re-taguear por URL."""

    def __init__(self, poster, marker: str = DEFAULT_MARKER, dedup=None):
        super().__init__(
            poster,
            link_re=_SHOPEE_RE,
            marker=marker,
            prefix="shopee",
            platform="Shopee",
            dedup=dedup,
        )
