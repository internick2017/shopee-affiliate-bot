"""Extrae la lista de ofertas de Amazon de un mensaje de promo.

Un mensaje puede traer varios productos, y los canales usan formatos distintos para
ello. Estas reglas salen de los 6 mensajes multi-link reales de Crowman e IAchados:

1. **Variantes etiquetadas** — un solo precio y varios links, cada uno con su etiqueta
   en la misma línea ("AA Pequena: <link>"). Una oferta por variante, nombre
   `base — etiqueta`, precio compartido (así lo presenta el canal).

2. **Una oferta por línea de precio** — el caso general. El link de cada oferta es el
   primer link de Amazon entre su línea de precio y la siguiente. Si en esa ventana hay
   links pero ninguno de Amazon, la oferta es de otra plataforma y se descarta. Si no
   hay ningún link (listas donde los links van todos al final), se toma el primer link
   de Amazon posterior.

Lo que NO se infiere, a propósito: un link sin precio propio no hereda el precio de
otra oferta. Publicar un precio equivocado es peor que publicar un post de menos.
"""
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

from .amazon_retagger import extract_amazon_links, extract_asin
from .prices import extract_price_info, is_price_line, price_start
from .product_name_extractor import _is_noise_line, _clean_candidate

_URL_RE = re.compile(r"https?://\S+")
_LEADING_SYMBOLS_RE = re.compile(r"^[^0-9A-Za-zÀ-ÿ]+")
_TRAILING_SEPARATORS = " -–—:|·•"

# Un nombre en la línea de precio tiene que ser un nombre, no la palabra que introduce
# el precio ("Por: R$ 6,66", "a partir de 28,39").
_PRICE_WORDS = {"por", "de", "a partir de", "preco", "preço", "valor", "apenas", "agora"}
# Etiquetas de link que no distinguen una variante de otra.
_GENERIC_LABELS = {"compre em", "compre aqui", "comprar", "compre", "link", "links", "aqui"}
_MIN_NAME_LETTERS = 3


@dataclass(frozen=True)
class Offer:
    name: str
    price_final: Decimal
    price_original: Optional[Decimal]
    is_range: bool
    url: str


def _strip(text: str) -> str:
    return _LEADING_SYMBOLS_RE.sub("", text).strip().strip(_TRAILING_SEPARATORS).strip()


def _letters(text: str) -> int:
    return sum(1 for ch in text if ch.isalpha())


def _inline_name(line: str) -> Optional[str]:
    """El nombre del producto cuando comparte línea con el precio ("The Last of Us - R$ 49")."""
    start = price_start(line)
    if start is None or start == 0:
        return None
    candidate = _strip(line[:start])
    if _letters(candidate) < _MIN_NAME_LETTERS:
        return None
    if candidate.lower() in _PRICE_WORDS:
        return None
    return _clean_candidate(candidate)


def _name_above(lines: List[str], index: int) -> Optional[str]:
    """La línea no-ruido más cercana por encima de `index`."""
    for j in range(index - 1, -1, -1):
        if not _is_noise_line(lines[j]):
            cleaned = _clean_candidate(lines[j])
            return cleaned or None
    return None


def _variant_label(line: str) -> Optional[str]:
    """La etiqueta que precede al link en su propia línea ("AA Pequena: <link>")."""
    match = _URL_RE.search(line)
    if not match:
        return None
    label = _strip(line[: match.start()])
    if _letters(label) < 2 or label.lower() in _GENERIC_LABELS:
        return None
    return label


def _first_amazon_link(lines: List[str]) -> Optional[str]:
    for line in lines:
        links = extract_amazon_links(line)
        if links:
            return links[0]
    return None


def _has_any_link(lines: List[str]) -> bool:
    return any(_URL_RE.search(line) for line in lines)


def _offer(name, line, url) -> Optional[Offer]:
    final, original, is_range = extract_price_info(line)
    if final is None or not name or not extract_asin(url):
        return None
    return Offer(name=name, price_final=final, price_original=original,
                 is_range=is_range, url=url)


def _dedupe_by_asin(offers: List[Offer]) -> List[Offer]:
    seen, unique = set(), []
    for offer in offers:
        asin = extract_asin(offer.url)
        if asin in seen:
            continue
        seen.add(asin)
        unique.append(offer)
    return unique


def _variant_offers(lines, price_index, link_indexes) -> List[Offer]:
    """Un precio + varios links etiquetados -> una oferta por variante."""
    labels = [_variant_label(lines[i]) for i in link_indexes]
    if not all(labels):
        return []
    base = _name_above(lines, price_index)
    if not base:
        return []
    offers = []
    for i, label in zip(link_indexes, labels):
        url = extract_amazon_links(lines[i])[0]
        offer = _offer(f"{base} — {label}", lines[price_index], url)
        if offer:
            offers.append(offer)
    return offers


def extract_offers(text: Optional[str]) -> List[Offer]:
    """Todas las ofertas de Amazon del mensaje, en orden de aparición."""
    if not text:
        return []
    # Se limpian los bordes: Promocasinha separa nombre y precio con una línea que
    # contiene un espacio, y `_is_noise_line(" ")` no la considera ruido — sin el
    # strip, ese espacio se tomaría como el nombre del producto.
    lines = [line.strip() for line in text.split("\n")]

    price_indexes = [i for i, line in enumerate(lines) if is_price_line(line)]
    if not price_indexes:
        return []
    link_indexes = [i for i, line in enumerate(lines) if extract_amazon_links(line)]
    if not link_indexes:
        return []

    if len(price_indexes) == 1 and len(link_indexes) > 1:
        variants = _variant_offers(lines, price_indexes[0], link_indexes)
        if variants:
            return _dedupe_by_asin(variants)

    offers = []
    for position, index in enumerate(price_indexes):
        end = price_indexes[position + 1] if position + 1 < len(price_indexes) else len(lines)
        window = lines[index:end]

        url = _first_amazon_link(window)
        if url is None:
            if _has_any_link(window):
                continue  # la oferta tiene link, pero es de otra plataforma
            url = _first_amazon_link(lines[index:])
            if url is None:
                continue

        name = _inline_name(lines[index]) or _name_above(lines, index)
        offer = _offer(name, lines[index], url)
        if offer:
            offers.append(offer)

    return _dedupe_by_asin(offers)
