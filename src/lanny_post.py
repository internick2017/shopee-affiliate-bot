from typing import Optional

from .amazon_retagger import extract_amazon_links, has_mercadolivre_links, retag_amazon_url
from .models import Product
from .post_builder import build_post
from .prices import extract_price, parse_br_number
from .product_name_extractor import extract_product_names

# Back-compat: tests importan `_parse_br_number` y `extract_price` desde este módulo.
_parse_br_number = parse_br_number

__all__ = ["extract_price", "build_lanny_amazon_post"]


def build_lanny_amazon_post(text: str, tag: str, hook: str) -> Optional[str]:
    """Arma un post de Amazon con el estilo (template + ganchos) de Lanny.

    Devuelve None si no hay links de Amazon, si hay links de Mercado Livre,
    si no se puede extraer un nombre de producto, o si no se puede extraer un precio.
    """
    amazon_links = extract_amazon_links(text)
    if not amazon_links:
        return None
    if has_mercadolivre_links(text):
        return None

    names = extract_product_names(text)
    if not names:
        return None

    final, original = extract_price(text)
    if final is None:
        return None

    link = retag_amazon_url(amazon_links[0], tag)

    product = Product(
        item_id=0,
        shop_id=0,
        name=names[0],
        price_final=final,
        image_url="",
        price_original=original,
        affiliate_link=link,
    )

    return build_post(product, hook)
