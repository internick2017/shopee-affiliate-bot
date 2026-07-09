from typing import List, Optional

from .amazon_retagger import retag_amazon_url
from .models import Product
from .offers import Offer, extract_offers
from .post_builder import build_post
from .prices import extract_price, parse_br_number

# Back-compat: tests importan `_parse_br_number` y `extract_price` desde este módulo.
_parse_br_number = parse_br_number

__all__ = [
    "extract_price",
    "build_lanny_amazon_post",
    "build_post_from_offer",
    "build_lanny_posts",
]


def build_post_from_offer(offer: Offer, tag: str, hook: str) -> str:
    """Arma el post de una oferta con el estilo (template + ganchos) de Lanny."""
    product = Product(
        item_id=0,
        shop_id=0,
        name=offer.name,
        price_final=offer.price_final,
        image_url="",
        price_original=offer.price_original,
        is_price_range=offer.is_range,
        affiliate_link=retag_amazon_url(offer.url, tag),
    )
    return build_post(product, hook)


def build_lanny_posts(text: str, tag: str, hook: str) -> List[str]:
    """Un post por cada oferta de Amazon del mensaje (los canales postean varias)."""
    return [build_post_from_offer(offer, tag, hook) for offer in extract_offers(text)]


def build_lanny_amazon_post(text: str, tag: str, hook: str) -> Optional[str]:
    """El post de la primera oferta del mensaje, o None si no hay ninguna.

    Se conserva para el código que solo espera un post; `AmazonPipeline` usa
    `extract_offers` directamente para no perder los productos siguientes.
    """
    offers = extract_offers(text)
    if not offers:
        return None
    return build_post_from_offer(offers[0], tag, hook)
