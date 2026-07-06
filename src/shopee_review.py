import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Detecta links de Shopee Brasil: shopee.com.br, s.shopee.com.br, shp.ee (amplio).
_SHOPEE_RE = re.compile(
    r"https?://(?:[\w-]+\.)*shopee\.com\.br/\S+|https?://shp\.ee/\S+", re.IGNORECASE
)
# Mismos marcadores de footer del competidor que usa amazon_retagger.
_FOOTER_MARKERS = ("grupos de promos", "ctlinks.com.br")

DEFAULT_MARKER = "⚠️ SHOPEE: gerar link de afiliado e postar manual"


def has_shopee_links(text: Optional[str]) -> bool:
    """True si el texto contiene al menos un link de Shopee."""
    if not text:
        return False
    return bool(_SHOPEE_RE.search(text))


def build_shopee_review_message(text: Optional[str], marker: str = DEFAULT_MARKER) -> Optional[str]:
    """Si hay link de Shopee, arma el mensaje a revisar: marca + texto (sin footer del
    competidor). Devuelve None si no hay Shopee."""
    if not has_shopee_links(text):
        return None
    lines = text.split("\n")
    filtered = [
        line
        for line in lines
        if not any(marker_word in line.lower() for marker_word in _FOOTER_MARKERS)
    ]
    cleaned = "\n".join(filtered).strip("\n")
    return f"{marker}\n\n{cleaned}"


class ShopeeReviewPipeline:
    """Handler: reenvía las ofertas de Shopee al canal para monetizar a mano.
    Misma interfaz que AmazonPipeline: handle(text, chat_title) -> int (0 = no la manejó)."""

    def __init__(self, poster, marker: str = DEFAULT_MARKER):
        self._poster = poster
        self._marker = marker

    async def handle(self, text, chat_title=None) -> int:
        msg = build_shopee_review_message(text, self._marker)
        if not msg:
            return 0
        await self._poster.post_text(msg)
        logger.info("Oferta de Shopee reenviada al canal para revisar")
        return 1
