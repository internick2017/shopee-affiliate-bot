import re
from decimal import Decimal
from typing import Optional, Tuple

from .amazon_retagger import extract_amazon_links, has_mercadolivre_links, retag_amazon_url
from .models import Product
from .post_builder import build_post
from .product_name_extractor import extract_product_names

_DISCOUNT_RE = re.compile(r"de\s*r\$\s*([\d.,]+)\s*por\s*r\$\s*([\d.,]+)", re.IGNORECASE)
_PRICE_RS_RE = re.compile(r"r\$\s*([\d.,]+)", re.IGNORECASE)
_PRICE_PLAIN_RE = re.compile(
    r"\b(\d[\d.,]*)\s*(?:à vista|no pix|via pix|em até|parcelado)",
    re.IGNORECASE,
)


def _parse_br_number(s: str) -> Decimal:
    """Convierte un número en formato brasileño a Decimal.

    "2391"->2391 ; "82,06"->82.06 ; "1.289,10"->1289.10 ; "2.391"->2391
    """
    s = s.strip().replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(".", "")
    return Decimal(s)


def extract_price(text: str) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    """Extrae (precio_final, precio_original) de un texto de oferta.

    1. Intenta el patrón de descuento "De R$ X ... por R$ Y" -> original=X, final=Y.
    2. Si no, toma la PRIMERA ocurrencia de precio como final: "R$ <num>" o un
       "<num>" bruto inmediatamente seguido de (à vista|no pix|via pix|em até|parcelado).
    3. Si no encuentra nada -> (None, None).
    """
    discount_match = _DISCOUNT_RE.search(text)
    if discount_match:
        original = _parse_br_number(discount_match.group(1))
        final = _parse_br_number(discount_match.group(2))
        return (final, original)

    rs_match = _PRICE_RS_RE.search(text)
    plain_match = _PRICE_PLAIN_RE.search(text)

    candidates = [m for m in (rs_match, plain_match) if m is not None]
    if not candidates:
        return (None, None)

    earliest = min(candidates, key=lambda m: m.start())
    final = _parse_br_number(earliest.group(1))
    return (final, None)


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
