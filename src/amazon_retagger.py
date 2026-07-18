import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .links import AMAZON_LINK_RE
from .review_forward import FOOTER_MARKERS

_AMAZON_RE = AMAZON_LINK_RE
_MERCADOLIVRE_MARKERS = ("meli.la/", "mercadolivre.com")

# El ASIN identifica al producto: 10 caracteres alfanuméricos en mayúscula tras
# /dp/ o /gp/product/. Es la clave estable para deduplicar entre grupos, porque
# el mismo producto llega con query params distintos según quién lo postee.
# El lookahead (y no `[/?]|$`) acepta el ASIN seguido de puntuación de la frase:
# ".../dp/B07L5BPDV7." es un producto, no un link a ignorar.
_ASIN_RE = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?![A-Za-z0-9])")


def extract_amazon_links(text: str | None) -> list[str]:
    """Devuelve todos los links de Amazon Brasil (amazon.com.br/...) en el texto."""
    if not text:
        return []
    return _AMAZON_RE.findall(text)


def extract_asin(url: str | None) -> str | None:
    """Devuelve el ASIN de una URL de producto de Amazon, o None si la URL no
    apunta a un producto (p. ej. un link a la home en un post de cupón)."""
    if not url:
        return None
    match = _ASIN_RE.search(url)
    return match.group(1) if match else None


def retag_amazon_url(url: str, tag: str) -> str:
    """Reemplaza (o agrega) el parámetro `tag` de la URL, preservando el resto de los query params."""
    parts = urlsplit(url)
    query_pairs = parse_qsl(parts.query, keep_blank_values=True)

    replaced = False
    new_pairs = []
    for key, value in query_pairs:
        if key == "tag":
            new_pairs.append((key, tag))
            replaced = True
        else:
            new_pairs.append((key, value))
    if not replaced:
        new_pairs.append(("tag", tag))

    new_query = urlencode(new_pairs)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


def has_mercadolivre_links(text: str | None) -> bool:
    """True si el texto contiene un link de Mercado Livre (meli.la/ o mercadolivre.com)."""
    if not text:
        return False
    return any(marker in text for marker in _MERCADOLIVRE_MARKERS)


def build_amazon_post(text: str | None, tag: str) -> str | None:
    """Arma el post listo para publicar: retaggea los links de Amazon y quita el footer del competidor.

    Devuelve None si no hay links de Amazon para monetizar, o si el mensaje incluye
    links de Mercado Livre (que no se pueden retaggear en v1).
    """
    amazon_links = extract_amazon_links(text)
    if not amazon_links:
        return None
    if has_mercadolivre_links(text):
        return None

    assert text is not None
    result = text
    for link in amazon_links:
        result = result.replace(link, retag_amazon_url(link, tag))

    lines = result.split("\n")
    filtered_lines = [
        line
        for line in lines
        if not any(marker in line.lower() for marker in FOOTER_MARKERS)
    ]
    result = "\n".join(filtered_lines)

    return result.strip("\n")
