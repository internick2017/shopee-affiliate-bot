import re
from typing import Callable, Tuple

import requests

# Patrón común de URL de producto: ...-i.{shopId}.{itemId}
_DASH_I_RE = re.compile(r"i\.(\d+)\.(\d+)")
# Patrón alternativo: /product/{shopId}/{itemId}
_PRODUCT_PATH_RE = re.compile(r"/product/(\d+)/(\d+)")


def _default_get(url: str):
    return requests.get(url, allow_redirects=True, timeout=15)


def resolve_shortlink(
    url: str,
    *,
    http_get: Callable[..., object] = _default_get,
) -> Tuple[int, int]:
    """Sigue el redirect de un shortlink de Shopee y devuelve (shop_id, item_id).

    Lanza ValueError si la URL final no contiene los IDs.
    """
    resp = http_get(url)
    final_url = getattr(resp, "url", "") or ""

    match = _DASH_I_RE.search(final_url)
    if match:
        return int(match.group(1)), int(match.group(2))

    match = _PRODUCT_PATH_RE.search(final_url)
    if match:
        return int(match.group(1)), int(match.group(2))

    raise ValueError(f"No se pudo extraer shop_id/item_id de: {final_url}")
