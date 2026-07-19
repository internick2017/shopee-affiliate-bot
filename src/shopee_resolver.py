"""Habla con la Affiliate Open API de Shopee (GraphQL, firmada) para resolver
shortlinks de Shopee a datos reales de producto y para re-taguear links a la cuenta
de Nick.

Los canales fuente postean shortlinks `s.shopee.com.br/XXXX` o `shp.ee/XXXX` que
redirigen a la página real del producto. La URL resuelta tiene distintas formas
(ver `_extract_product_ids`); con el `shopId`+`itemId` extraídos, `productOfferV2`
da nombre/precio/descuento Y un link ya trackeado a la cuenta de Nick, todo en una
sola llamada — no hace falta pedir el link aparte con `generateShortLink` para el
caso normal (verificado en vivo: el `offerLink` de `productOfferV2` lleva el mismo
`mmp_pid`/`utm_source` que un link generado explícitamente).

`generateShortLink` se usa acá solo para los links "extra" que acompañan al
producto (cupón/campaña VIP): son links de Shopee como cualquier otro, y la API
los re-tagea igual, sin importar que no sean un producto individual.
"""
import hashlib
import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import requests

from .links import SHOPEE_LINK_RE

logger = logging.getLogger(__name__)

_SHORTLINK_RE = SHOPEE_LINK_RE

_GRAPHQL_ENDPOINT = "https://open-api.affiliate.shopee.com.br/graphql"

# Mismo motivo que en mercadolivre_resolver: seguir el redirect de un shortlink
# aterriza en la página real de Shopee, que filtra por User-Agent.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_TIMEOUT_SECONDS = 20

# Formato 1 (49% de los links reales medidos, 2026-07-18): ...-i.{shopId}.{itemId}
_FORMATO_1_RE = re.compile(r"-i\.(\d+)\.(\d+)(?:[/?]|$)")

# Formato 3 (28% de los links reales medidos — NO es un caso raro):
# /{vendedor}/{shopId}/{itemId}. Se excluye "product" como vendedor a propósito:
# ese es el formato 2 (/product/{shopId}/{itemId}), que en 97 links reales no
# apareció ni una vez — no se prioriza sin evidencia (ver spec, Riesgo aceptado).
_FORMATO_3_RE = re.compile(r"shopee\.com\.br/([\w.-]+)/(\d+)/(\d+)(?:[/?]|$)")

# Los links "extra" (no-producto) solo se retaguean y muestran como cupón si
# tienen esta forma — patrones reales vistos: /m/cupom-de-desconto, /m/sabadovip,
# /shopeevip. Cualquier otro no-producto (carrito, wallet, raíz del sitio) se
# ignora: etiquetarlo como cupón sin evidencia sería engañoso.
_CUPOM_LIKE_RE = re.compile(r"shopee\.com\.br/(?:m/\w|shopeevip)")


def _default_get(url: str):
    return requests.get(
        url,
        headers={"User-Agent": _USER_AGENT},
        timeout=_TIMEOUT_SECONDS,
        allow_redirects=True,
    )


def _firmar(app_id: str, secret: str, payload: str) -> tuple[str, str]:
    """Timestamp (segundos) y firma SHA256(AppId + Timestamp + Payload + Secret),
    concatenación sin separadores — esquema oficial de Shopee, verificado en vivo."""
    ts = str(int(time.time()))
    sig = hashlib.sha256(f"{app_id}{ts}{payload}{secret}".encode()).hexdigest()
    return ts, sig


def _default_post(url: str, *, data: str, headers: dict):
    return requests.post(url, data=data, headers=headers, timeout=_TIMEOUT_SECONDS)


def _graphql_call(
    app_id: str,
    secret: str,
    query: str,
    *,
    http_post: Callable[..., object] = _default_post,
) -> dict | None:
    """POST firmado a la API. Devuelve `data` en éxito, None ante cualquier fallo
    (red, HTTP != 200, o `errors` en el body — nunca se distingue el código de
    error acá, todos degradan igual). Nunca lanza."""
    payload = json.dumps({"query": query, "variables": {}}, separators=(",", ":"))
    ts, sig = _firmar(app_id, secret, payload)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={app_id}, Timestamp={ts}, Signature={sig}",
    }
    try:
        response = http_post(_GRAPHQL_ENDPOINT, data=payload, headers=headers)
        if response.status_code != 200:
            return None
        body = response.json()
        if not isinstance(body, dict):
            logger.warning("La API de Shopee devolvió un JSON que no es un diccionario: %s", type(body))
            return None
    except Exception as exc:  # noqa: BLE001 - degradación segura, se loguea
        logger.warning("Fallo llamando a la API de Shopee: %s", exc)
        return None
    if "errors" in body:
        logger.info("La API de Shopee devolvió error: %s", body["errors"])
        return None
    return body.get("data")


def extract_shopee_shortlinks(text: str | None) -> list[str]:
    """Devuelve todos los links de Shopee del texto, en orden de aparición."""
    if not text:
        return []
    return _SHORTLINK_RE.findall(text)


def _extract_product_ids(url: str) -> tuple[int, int] | None:
    """(shopId, itemId) probando el formato 1 y después el 3. None si no matchea
    ninguno (cupón, VIP, carrito, wallet, raíz del sitio, o formato 2 sin evidencia
    real — ver Global Constraints)."""
    m1 = _FORMATO_1_RE.search(url)
    if m1:
        return int(m1.group(1)), int(m1.group(2))
    m3 = _FORMATO_3_RE.search(url)
    if m3 and m3.group(1) != "product":
        return int(m3.group(2)), int(m3.group(3))
    return None


def es_link_tipo_cupom(url: str) -> bool:
    """True si la URL resuelta tiene forma de cupón/campaña (/m/..., /shopeevip).
    Usado para decidir qué links no-producto vale la pena re-taguear y mostrar."""
    return bool(_CUPOM_LIKE_RE.search(url))


def _resolve_redirect(
    shortlink: str, *, http_get: Callable[..., object] = _default_get
) -> str | None:
    """Sigue el redirect real y devuelve la URL final. None ante cualquier fallo de
    red. Nunca lanza."""
    try:
        response = http_get(shortlink)
        close = getattr(response, "close", None)
        if callable(close):
            close()
        return response.url
    except Exception as exc:  # noqa: BLE001 - degradación segura, se loguea
        logger.warning("No se pudo resolver el link de Shopee %s: %s", shortlink, exc)
        return None


def _a_decimal(valor) -> Decimal | None:
    """`Decimal(str(valor))`, nunca `Decimal(valor)` directo sobre un float."""
    if valor is None:
        return None
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return None


def _precio_previo_derivado(precio: Decimal, pct: int) -> Decimal | None:
    """`productOfferV2` no da el precio original, solo el actual + el % de
    descuento (entero). Se deriva el previo invirtiendo la fórmula del %:
    previo = precio / (1 - pct/100). Es una aproximación (Shopee redondea el % a
    entero, así que el inverso no es exacto al centavo) — verificado contra 4
    productos reales el 2026-07-18, el % recalculado siempre coincidió."""
    if pct <= 0 or pct >= 100:
        return None
    factor = Decimal(100 - pct) / Decimal(100)
    return (precio / factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class ShopeeOffer:
    """Datos reales del producto, leídos de la Affiliate Open API al momento de
    publicar."""

    titulo: str
    precio: Decimal
    descuento_pct: int
    link_propio: str
    precio_previo: Decimal | None = None

    @property
    def tiene_descuento(self) -> bool:
        return self.descuento_pct > 0


def resolve_shopee_offer(
    shortlink: str,
    app_id: str,
    secret: str,
    *,
    http_get: Callable[..., object] = _default_get,
    http_post: Callable[..., object] = _default_post,
) -> ShopeeOffer | None:
    """Título, precio y descuento reales del producto detrás del shortlink.

    None si: la red falla, la URL resuelta no tiene forma de producto (formato 1 o
    3), o `productOfferV2` no tiene datos de ese item. Nunca lanza.
    """
    url = _resolve_redirect(shortlink, http_get=http_get)
    if not url:
        return None

    ids = _extract_product_ids(url)
    if not ids:
        return None
    shop_id, item_id = ids

    query = f"""
    query {{
      productOfferV2(itemId: {item_id}, shopId: {shop_id}, limit: 1) {{
        nodes {{ productName price priceDiscountRate offerLink }}
      }}
    }}
    """
    data = _graphql_call(app_id, secret, query, http_post=http_post)
    if not data:
        return None

    nodes = (data.get("productOfferV2") or {}).get("nodes") or []
    if not nodes:
        return None
    nodo = nodes[0]

    titulo = nodo.get("productName")
    precio = _a_decimal(nodo.get("price"))
    link_propio = nodo.get("offerLink")
    if not titulo or precio is None or not link_propio:
        return None

    pct = nodo.get("priceDiscountRate") or 0
    return ShopeeOffer(
        titulo=titulo,
        precio=precio,
        descuento_pct=pct,
        link_propio=link_propio,
        precio_previo=_precio_previo_derivado(precio, pct),
    )


def retag_shopee_url(
    url: str,
    app_id: str,
    secret: str,
    subids: list[str],
    *,
    http_post: Callable[..., object] = _default_post,
) -> str | None:
    """Re-tagea CUALQUIER URL de Shopee a la cuenta de Nick (no solo productos —
    verificado en vivo con un link de campaña VIP, funciona igual). None ante
    cualquier fallo. Nunca lanza."""
    sub_ids_json = json.dumps(subids)
    query = f"""
    mutation {{
      generateShortLink(input: {{originUrl: "{url}", subIds: {sub_ids_json}}}) {{
        shortLink
      }}
    }}
    """
    data = _graphql_call(app_id, secret, query, http_post=http_post)
    if not data:
        return None
    return (data.get("generateShortLink") or {}).get("shortLink")
