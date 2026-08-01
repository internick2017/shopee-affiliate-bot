"""Resuelve shortlinks de Mercado Livre (`meli.la/...`) a la URL real del producto.

Los canales fuente postean `meli.la/XXXX`, que redirige a
`mercadolivre.com.br/social/<afiliado>?ref=<blob cifrado>`. El `ref` no se puede
reescribir (está firmado a la cuenta que lo generó), pero la página resuelta trae
embebido un JSON interno de tracking (`melidataSocial`) con el item_id real del
producto compartido — validado contra 43 links reales, 91% de éxito (ver
docs/superpowers/specs/2026-07-14-mercadolivre-auto-retag-design.md).

El item_id NO siempre es un ID de catálogo compatible con `/p/{item_id}`: a veces es
el ID crudo de un anuncio individual sin ficha de catálogo compartida, y en ese caso
`/p/` da 404 (bug encontrado en producción el 2026-07-17, ~58% de los posts afectados
— ver docs/superpowers/specs/2026-07-17-mercadolivre-canonical-url-fix-design.md). La
solución: el mismo JSON trae, en el bloque `metadata` cuyo "id" coincide con el
item_id, un campo "url" con la ruta REAL del producto (`/up/{user_product_id}`,
`produto.mercadolivre.com.br/MLB-{id}-slug`, o un deep-link `ddnf.adj.st` que hay que
desenvolver). Cuando no se encuentra ese campo (típicamente porque el item_id YA es un
ID de catálogo), se cae al `/p/{item_id}` de siempre, que funciona para ese caso.
"""
import json
import logging
import re
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode, urlsplit, urlunsplit

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

# Ventana de búsqueda tras el "url" para encontrar el "url_params" adyacente cuando el
# url es un deep-link de Adjust (ddnf.adj.st) — los dos campos están uno al lado del
# otro en el JSON real observado, 600 chars alcanza con margen.
_ADJST_WINDOW = 600


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


def _extract_item_id(body: str) -> str | None:
    """Extrae y valida el formato del item_id embebido en el body. None si no hay
    match, si viene vacío, o si el formato no es MLB + dígitos."""
    match = _ITEM_ID_RE.search(body)
    item_id = match.group(1) if match else ""
    if not _VALID_ITEM_ID_RE.fullmatch(item_id):
        return None
    return item_id


def _extract_canonical_url(item_id: str, body: str) -> str | None:
    """Busca el bloque metadata cuyo "id" coincide con item_id y devuelve su "url".

    Si el "url" es un deep-link de Adjust (ddnf.adj.st), lo desenvuelve buscando el
    parámetro `url=` dentro del "url_params" adyacente. None si no encuentra nada en
    ningún paso — típicamente porque item_id YA es un ID de catálogo (no tiene una
    entrada de recomendación propia en la página, y no hace falta: /p/{item_id} ya
    funciona directo para ese caso).
    """
    match = re.search(
        r'"id":"' + re.escape(item_id) + r'"(?:(?!\}).)*?"url":"([^"]*)"', body
    )
    if not match:
        return None
    raw_url = match.group(1).replace("\\u002F", "/").replace("\\/", "/")

    if "adj.st" not in raw_url:
        return raw_url if raw_url.startswith("http") else f"https://{raw_url}"

    window = body[match.end() : match.end() + _ADJST_WINDOW]
    params_match = re.search(r'"url_params":"([^"]*)"', window)
    if not params_match:
        return None
    params_raw = params_match.group(1).replace("\\u0026", "&").replace("\\/", "/")
    inner_match = re.search(r"[?&]url=([^&\"]+)", params_raw)
    if not inner_match:
        return None
    return urllib.parse.unquote(inner_match.group(1))


def resolve_mercadolivre_item(
    url: str,
    *,
    http_get: Callable[..., object] = _default_get,
) -> str | None:
    """Sigue el redirect y devuelve el item_id (MLB...) del producto compartido.

    Devuelve None si la red falla, si la página no trae el bloque melidataSocial
    (p. ej. un link de "lista" en vez de producto puntual), o si item_id viene
    vacío o con formato inesperado. Nunca lanza: un shortlink roto no debe tumbar el bot.
    """
    try:
        response = http_get(url)
        body = getattr(response, "text", "") or ""
        close = getattr(response, "close", None)
        if callable(close):
            close()
        item_id = _extract_item_id(body)
        if not item_id:
            logger.info(
                "El link %s no trajo un item_id resoluble (no es producto puntual)", url
            )
        return item_id
    except Exception as exc:
        logger.warning("No se pudo resolver el link de Mercado Livre %s: %s", url, exc)
        return None


def resolve_mercadolivre_url(
    url: str,
    *,
    http_get: Callable[..., object] = _default_get,
) -> str | None:
    """Sigue el redirect y devuelve la URL BASE (sin matt_word/matt_tool) del producto
    compartido: la ruta real (/p/, /up/, produto.mercadolivre.com.br) cuando se puede
    encontrar, o el fallback /p/{item_id} cuando no (item_id de catálogo). None si no
    se pudo resolver ningún producto. Nunca lanza.
    """
    try:
        response = http_get(url)
        body = getattr(response, "text", "") or ""
        close = getattr(response, "close", None)
        if callable(close):
            close()
        item_id = _extract_item_id(body)
        if not item_id:
            logger.info(
                "El link %s no trajo un item_id resoluble (no es producto puntual)", url
            )
            return None
        canonical = _extract_canonical_url(item_id, body)
        if canonical:
            return canonical
        return f"https://www.mercadolivre.com.br/p/{item_id}"
    except Exception as exc:
        logger.warning("No se pudo resolver el link de Mercado Livre %s: %s", url, exc)
        return None


def retag_mercadolivre_url(base_url: str, matt_word: str, matt_tool: str) -> str:
    """Agrega matt_word/matt_tool a la URL base del producto, descartando cualquier
    query string o fragment que ya tuviera (tracking propio de Mercado Livre, no
    nuestro) — igual de limpio que amazon_shortlink canonicalizando a dp/{ASIN}."""
    parts = urlsplit(base_url)
    query = urlencode({"matt_word": matt_word, "matt_tool": matt_tool})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


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
        base_url = resolve_mercadolivre_url(link, http_get=http_get)
        if not base_url:
            return None
        resolved[link] = retag_mercadolivre_url(base_url, matt_word, matt_tool)
    return resolved


@dataclass
class MercadoLivreOffer:
    """Datos reales del producto, leídos de la página de ML al momento de publicar."""

    titulo: str
    precio: Decimal
    url_canonica: str
    precio_previo: Decimal | None = None
    descuento: str | None = None

    @property
    def tiene_descuento(self) -> bool:
        """Sin descuento comprobable no es una oferta y no se publica como tal."""
        if self.descuento:
            return True
        return self.precio_previo is not None and self.precio_previo > self.precio


def _extract_polycard(item_id: str, body: str) -> dict | None:
    """Devuelve el polycard cuyo metadata.id coincide con item_id, ya parseado.

    `json.loads` directo sobre `body`: no hace falta desescapar nada, las comillas de
    esta página ya son reales (verificado contra la web viva, no es una suposición).
    Se ubica el bloque por posición (buscando el `"id":"<item_id>"` y retrocediendo
    hasta el `{"unique_id"` que lo contiene) y se parsea con conteo de llaves
    balanceadas, en vez de con una regex de campos sueltos: la forma interna de cada
    componente varía (`price` puede colgar directo del bloque o de más adentro) y una
    regex sobre una ventana fija se rompe con esas variaciones.
    """
    idx = body.find(f'"id":"{item_id}"')
    if idx < 0:
        return None
    start = body.rfind('{"unique_id"', max(0, idx - 20000), idx)
    if start < 0:
        return None
    depth = 0
    for i in range(start, min(len(body), start + 40000)):
        if body[i] == "{":
            depth += 1
        elif body[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(body[start : i + 1])
                except ValueError:
                    return None
    return None


def _buscar(obj, clave: str):
    """Primera aparición de `clave` en cualquier nivel del dict/list.

    Revisa las claves del nivel actual ANTES de bajar a los hijos. Es lo que evita
    confundir el precio real (`components[2]["price"]`, directo) con el precio total
    de las cuotas, que vive mucho más adentro
    (`components[2]["price"]["installments"]["values"][1]["price"]`): al encontrar
    `"price"` en el nivel de arriba, se devuelve ahí mismo sin seguir bajando.
    """
    if isinstance(obj, dict):
        if clave in obj:
            return obj[clave]
        for valor in obj.values():
            hallado = _buscar(valor, clave)
            if hallado is not None:
                return hallado
    elif isinstance(obj, list):
        for valor in obj:
            hallado = _buscar(valor, clave)
            if hallado is not None:
                return hallado
    return None


def _a_decimal(valor) -> Decimal | None:
    """`Decimal(str(valor))`, nunca `Decimal(valor)` directo: un float como 284.99
    no es exacto en binario, y pasarlo crudo a Decimal arrastra ese error."""
    if valor is None:
        return None
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return None


def resolve_mercadolivre_offer(
    url: str, *, http_get=_default_get
) -> MercadoLivreOffer | None:
    """Título, precio y descuento reales del producto detrás del shortlink.

    Un solo fetch, el mismo que ya se hacía para resolver la URL. None si algo falta:
    el caller cae al reenvío manual. Nunca lanza.
    """
    try:
        response = http_get(url)
        try:
            body = response.text
        finally:
            close = getattr(response, "close", None)
            if close is not None:
                close()
    except Exception as exc:  # noqa: BLE001 - degradación segura, se loguea
        logger.warning("No se pudo resolver el link de Mercado Livre %s: %s", url, exc)
        return None

    try:
        item_id = _extract_item_id(body)
        if not item_id:
            return None
        card = _extract_polycard(item_id, body)
        if not card:
            return None

        titulo_obj = _buscar(card, "title")
        titulo = titulo_obj.get("text") if isinstance(titulo_obj, dict) else None
        precio_obj = _buscar(card, "price")
        if not isinstance(precio_obj, dict) or not titulo:
            return None

        actual = precio_obj.get("current_price")
        precio = _a_decimal(
            actual.get("value") if isinstance(actual, dict) else precio_obj.get("value")
        )
        if precio is None:
            return None

        previo_obj = precio_obj.get("previous_price")
        precio_previo = _a_decimal(
            previo_obj.get("value") if isinstance(previo_obj, dict) else None
        )
        etiqueta = _buscar(card, "discount_label")
        descuento = etiqueta.get("text") if isinstance(etiqueta, dict) else None

        metadata = card.get("metadata") or {}
        ruta = metadata.get("url")
        if not ruta:
            return None
        if "adj.st" in ruta:
            # Deep-link de Adjust sin desenvolver. _extract_canonical_url (más abajo en
            # este módulo) sí lo desenvuelve para el camino viejo
            # (resolve_mercadolivre_url); acá se prefiere degradar a None y caer al
            # reenvío marcado antes que duplicar esa lógica para un caso que, en la
            # medición real de 50 links (2026-07-18), no se dio ni una vez. Publicar el
            # deep-link tal cual sería peor que no publicar nada: un link roto con la
            # marca propia encima.
            return None
        canonica = ruta if ruta.startswith("http") else f"https://{ruta}"

        return MercadoLivreOffer(
            titulo=titulo,
            precio=precio,
            url_canonica=canonica,
            precio_previo=precio_previo,
            descuento=descuento,
        )
    except Exception as exc:  # noqa: BLE001 - el formato es interno de ML, puede cambiar
        logger.warning("No se pudo leer el producto de Mercado Livre %s: %s", url, exc)
        return None
