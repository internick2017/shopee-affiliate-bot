"""Fuente única de los patrones de link, como `prices.py` lo es de los precios.

Nadie más define regexes de URL: los handlers importan de acá. Así `review_forward`
puede saber qué links son "de otra plataforma" sin importar a los handlers (que a su
vez lo importan a él).
"""

import re

# Un link termina donde termina la URL, no donde termina la palabra. `\S+` se tragaba
# la puntuación de la frase ("...dp/B07L5BPDV7." o "...(ver acá)"), y esa URL con el
# punto pegado ni matchea el ASIN ni funciona si se postea.
_URL_TAIL = r"\S*[^\s.,;:!?)\]}>\"'”’»]"

# Amazon Brasil. Sin IGNORECASE a propósito: el ASIN es mayúsculas y el path también.
AMAZON_LINK_RE = re.compile(r"https?://(?:[\w-]+\.)*amazon\.com\.br/" + _URL_TAIL)

# `link.amazon/XXX` (shortener propio) y `amzn.to/XXX` (bit.ly de Amazon). El token
# del path no es el ASIN: hay que seguir el redirect (ver `amazon_shortlink.py`).
AMAZON_SHORTLINK_RE = re.compile(r"https?://link\.amazon/\w+|https?://amzn\.to/\w+", re.IGNORECASE)

# shopee.com.br, s.shopee.com.br y el shortener shp.ee.
SHOPEE_LINK_RE = re.compile(
    r"https?://(?:[\w-]+\.)*shopee\.com\.br/" + _URL_TAIL + r"|https?://shp\.ee/" + _URL_TAIL,
    re.IGNORECASE,
)

# meli.la (shortlink) y el link largo mercadolivre.com / mercadolivre.com.br.
MERCADOLIVRE_LINK_RE = re.compile(
    r"https?://meli\.la/"
    + _URL_TAIL
    + r"|https?://(?:[\w-]+\.)*mercadolivre\.com(?:\.br)?/"
    + _URL_TAIL,
    re.IGNORECASE,
)

# meli.la (shortlink). Distinto de MERCADOLIVRE_LINK_RE: acá solo el shortlink, que es
# el único formato que hace falta resolver (un link largo ya expone el MLB en el path).
MELI_SHORTLINK_RE = re.compile(r"https?://meli\.la/" + _URL_TAIL, re.IGNORECASE)

# Una plataforma puede reclamar por más de un patrón: un `link.amazon/...` sin resolver
# sigue siendo un producto de Amazon a los ojos de los otros handlers.
PLATFORM_LINK_RES: dict[str, tuple[re.Pattern, ...]] = {
    "amazon": (AMAZON_LINK_RE, AMAZON_SHORTLINK_RE),
    "shopee": (SHOPEE_LINK_RE,),
    "ml": (MERCADOLIVRE_LINK_RE,),
}


def foreign_link_res(platform: str | None) -> tuple[re.Pattern, ...]:
    """Los patrones de todas las plataformas MENOS la dada. `None` -> ninguno."""
    if platform is None:
        return ()
    return tuple(
        pattern
        for key, patterns in PLATFORM_LINK_RES.items()
        if key != platform
        for pattern in patterns
    )


def has_any_link(text: str | None, patterns: tuple[re.Pattern, ...]) -> bool:
    """True si el texto contiene al menos un link de alguno de los patrones."""
    if not text:
        return False
    return any(pattern.search(text) for pattern in patterns)
