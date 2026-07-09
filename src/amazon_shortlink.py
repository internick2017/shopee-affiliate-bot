"""Resuelve shortlinks de Amazon (`link.amazon/...`, `amzn.to/...`) a la URL del producto.

Promocasinha no postea `amazon.com.br/dp/...`, postea `https://link.amazon/B0iFvhSgZ`.
El token del path NO es el ASIN: hay que seguir el redirect para saber qué producto es.
La URL final trae el tag y la atribución del afiliado de origen, así que se canonicaliza
a `amazon.com.br/dp/{ASIN}` — re-taguear encima no borraría `ascsubtag`/`btn_ref`.
"""
import logging
import re
from typing import Callable, Dict, List, Optional

import requests

from .amazon_retagger import extract_asin

logger = logging.getLogger(__name__)

# `link.amazon/XXX` (shortener propio de Amazon) y `amzn.to/XXX` (bit.ly de Amazon).
_SHORTLINK_RE = re.compile(
    r"https?://link\.amazon/\w+|https?://amzn\.to/\w+", re.IGNORECASE
)

_TIMEOUT_SECONDS = 15


def _default_get(url: str):
    # stream=True: solo necesitamos la URL final del redirect, no el HTML.
    return requests.get(url, allow_redirects=True, timeout=_TIMEOUT_SECONDS, stream=True)


def has_amazon_shortlinks(text: Optional[str]) -> bool:
    """True si el texto contiene al menos un shortlink de Amazon."""
    if not text:
        return False
    return bool(_SHORTLINK_RE.search(text))


def extract_amazon_shortlinks(text: Optional[str]) -> List[str]:
    """Devuelve todos los shortlinks de Amazon del texto, en orden de aparición."""
    if not text:
        return []
    return _SHORTLINK_RE.findall(text)


def resolve_amazon_shortlink(
    url: str,
    *,
    http_get: Callable[..., object] = _default_get,
) -> Optional[str]:
    """Sigue el redirect y devuelve `https://www.amazon.com.br/dp/{ASIN}`.

    Devuelve None si la red falla o si el destino no es una página de producto
    (p. ej. la oferta cayó y redirige a la home). Nunca lanza: un shortlink roto
    no debe tumbar el bot.
    """
    try:
        response = http_get(url)
    except Exception as exc:
        logger.warning("No se pudo resolver el shortlink %s: %s", url, exc)
        return None

    final_url = getattr(response, "url", "") or ""
    close = getattr(response, "close", None)
    if callable(close):
        close()

    asin = extract_asin(final_url)
    if not asin:
        logger.info("El shortlink %s no llevó a un producto (%s)", url, final_url[:80])
        return None
    return f"https://www.amazon.com.br/dp/{asin}"


def expand_amazon_shortlinks(
    text: Optional[str],
    *,
    http_get: Callable[..., object] = _default_get,
) -> Optional[str]:
    """Reemplaza cada shortlink de Amazon por la URL canónica del producto.

    Los shortlinks que no resuelven se dejan como están (el resto del pipeline
    los ignora, porque no matchean `amazon.com.br`). Bloquea en I/O: llamar
    desde un thread, no desde el event loop.
    """
    if not has_amazon_shortlinks(text):
        return text

    resolved: Dict[str, Optional[str]] = {}
    result = text
    for short in extract_amazon_shortlinks(text):
        if short not in resolved:
            resolved[short] = resolve_amazon_shortlink(short, http_get=http_get)
        target = resolved[short]
        if target:
            result = result.replace(short, target)
    return result
