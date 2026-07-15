"""Resuelve shortlinks de Mercado Livre (`meli.la/...`) al item_id del producto.

Los canales fuente postean `meli.la/XXXX`, que redirige a
`mercadolivre.com.br/social/<afiliado>?ref=<blob cifrado>`. El `ref` no se puede
reescribir (está firmado a la cuenta que lo generó), pero la página resuelta trae
embebido un JSON interno de tracking (`melidataSocial`) con el item_id real del
producto compartido — validado contra 43 links reales, 91% de éxito (ver
docs/superpowers/specs/2026-07-14-mercadolivre-auto-retag-design.md).

Con el item_id en mano, el link propio se arma sin pasar por la Central de
Afiliados: mercadolivre.com.br/p/{item_id}?matt_word=...&matt_tool=...
"""
import logging
import re
from collections.abc import Callable

import requests

from .links import MELI_SHORTLINK_RE

logger = logging.getLogger(__name__)

_SHORTLINK_RE = MELI_SHORTLINK_RE

# El 403 de Mercado Livre es un filtro simple por string de User-Agent (confirmado:
# curl sin nada y python-requests dan 403; cualquier UA de navegador real pasa).
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_TIMEOUT_SECONDS = 15

# item_id es un campo interno no documentado del frontend de Mercado Livre (no una
# API pública): puede cambiar de formato sin aviso. Si deja de matchear, el efecto es
# degradación segura (build_own_mercadolivre_links devuelve None, cae a reenvío manual).
_ITEM_ID_RE = re.compile(r'"melidataSocial":\{[^}]*?"item_id":"([^"]*)"')

# Un item_id real de Mercado Livre siempre es "MLB" + dígitos. El regex de arriba
# captura cualquier corrida de no-comillas, así que esto valida el formato antes de
# interpolarlo en una URL pública.
_VALID_ITEM_ID_RE = re.compile(r"^MLB\d+$")


def _default_get(url: str):
    return requests.get(
        url,
        headers={"User-Agent": _USER_AGENT},
        timeout=_TIMEOUT_SECONDS,
        allow_redirects=True,
    )


def has_meli_shortlinks(text: str | None) -> bool:
    """True si el texto contiene al menos un shortlink meli.la."""
    if not text:
        return False
    return bool(_SHORTLINK_RE.search(text))


def extract_meli_shortlinks(text: str | None) -> list[str]:
    """Devuelve todos los shortlinks meli.la del texto, en orden de aparición."""
    if not text:
        return []
    return _SHORTLINK_RE.findall(text)


def resolve_mercadolivre_item(
    url: str,
    *,
    http_get: Callable[..., object] = _default_get,
) -> str | None:
    """Sigue el redirect y devuelve el item_id (MLB...) del producto compartido.

    Devuelve None si la red falla, si la página no trae el bloque melidataSocial
    (p. ej. un link de "lista" en vez de producto puntual), o si item_id viene
    vacío. Nunca lanza: un shortlink roto no debe tumbar el bot.
    """
    try:
        response = http_get(url)
        body = getattr(response, "text", "") or ""
        close = getattr(response, "close", None)
        if callable(close):
            close()

        match = _ITEM_ID_RE.search(body)
        if not match or not match.group(1):
            logger.info(
                "El link %s no trajo un item_id resoluble (no es producto puntual)", url
            )
            return None
        item_id = match.group(1)
        if not _VALID_ITEM_ID_RE.fullmatch(item_id):
            logger.warning(
                "El link %s trajo un item_id con formato inesperado (%r); se descarta",
                url,
                item_id,
            )
            return None
        return item_id
    except Exception as exc:
        logger.warning("No se pudo resolver el link de Mercado Livre %s: %s", url, exc)
        return None


def retag_mercadolivre_url(item_id: str, matt_word: str, matt_tool: str) -> str:
    """Arma el link propio: no hace falta pasar por la Central de Afiliados, alcanza
    con el item_id y los identificadores de campaña/cuenta de Nick."""
    return (
        f"https://www.mercadolivre.com.br/p/{item_id}"
        f"?matt_word={matt_word}&matt_tool={matt_tool}"
    )


def build_own_mercadolivre_links(
    text: str | None,
    matt_word: str,
    matt_tool: str,
    *,
    http_get: Callable[..., object] = _default_get,
) -> dict[str, str] | None:
    """Resuelve TODOS los shortlinks meli.la del texto a su link propio.

    Devuelve {shortlink: link_propio} si TODOS resolvieron. Devuelve None si no hay
    shortlinks, o si ALGUNO no resolvió (todo-o-nada: el caller debe caer al reenvío
    manual antes que publicar un post con una mezcla de links propios y ajenos).
    """
    shortlinks = extract_meli_shortlinks(text)
    if not shortlinks:
        return None

    resolved: dict[str, str] = {}
    for link in shortlinks:
        if link in resolved:
            continue
        item_id = resolve_mercadolivre_item(link, http_get=http_get)
        if not item_id:
            return None
        resolved[link] = retag_mercadolivre_url(item_id, matt_word, matt_tool)
    return resolved
