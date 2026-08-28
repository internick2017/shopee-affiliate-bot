"""Descubrimiento de productos para grabar: en vez de monetizar lo que las fuentes
postean, le pregunta al catálogo de Shopee qué conviene grabar.

Dos modos, los dos sobre `productOfferV2`:
  - por categoría: "dame lo mejor de limpieza" — trae cosas que a uno no se le
    hubieran ocurrido buscar;
  - por palabra clave: "organizador cozinha" — cuando ya se sabe qué se busca.

El ranking NO es por ventas a secas. Ordenar por ventas trae lo más saturado, que
todo el mundo ya publicó; el puntaje mezcla comisión (lo que se cobra), ventas
(prueba social), rating y precio bajo (compra por impulso). Los pesos están en
constantes justamente para poder moverlos sin tocar la lógica.

Los IDs de categoría se descubrieron sampleando la API (2026-08-27): no existe
query que devuelva el catálogo de categorías, así que se infirieron de los
`productCatIds` de productos reales y se verificaron mirando qué trae cada uno.
"""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from .shopee_resolver import _graphql_call

# Peso de cada factor en el puntaje. Comisión arriba de ventas a propósito: el
# producto más vendido suele ser el más saturado y el que peor paga.
_PESO_COMISION = 0.40
_PESO_VENTAS = 0.30
_PESO_RATING = 0.15
_PESO_PRECIO = 0.15

_COMISION_TECHO_PCT = 20.0   # arriba de esto el factor satura en 1
_VENTAS_TECHO_LOG = 5.0      # log10(100000): 100k ventas satura el factor
_PRECIO_IMPULSO = 30.0       # hasta acá, compra por impulso plena
_PRECIO_TECHO = 80.0         # arriba de acá el factor precio es 0

# Nombre real de cada categoría de nivel 1. Importa mostrarlo: los alias de abajo
# son más específicos que la categoría (un alias "limpeza" cae en toda la categoría
# Casa, que también trae ferramentas y jardim), y sin decirlo el usuario cree que
# filtró por algo que no filtró.
NOMBRES: dict[int, str] = {
    100636: "Casa e Cozinha",
    100630: "Beleza e Cuidados Pessoais",
    100632: "Bebês e Brinquedos",
    100013: "Celulares e Acessórios",
    100631: "Pet Shop",
    100009: "Acessórios de Moda",
    100644: "Informática",
    100629: "Alimentos e Bebidas",
    100001: "Saúde e Suplementos",
    100637: "Esportes e Lazer",
    102187: "Automotivo",
    100638: "Papelaria e Escritório",
    100017: "Moda Feminina",
    100535: "Áudio e Fones",
    100010: "Eletrodomésticos",
    100532: "Calçados",
}

# Alias que la gente escribe -> categoría de nivel 1 que los contiene.
# Varios alias caen en la misma categoría a propósito: Shopee no tiene una
# categoría "limpeza" de nivel 1, vive dentro de Casa e Cozinha.
CATEGORIAS: dict[str, int] = {
    "casa": 100636,
    "cozinha": 100636,
    "limpeza": 100636,
    "beleza": 100630,
    "bebe": 100632,
    "brinquedos": 100632,
    "celular": 100013,
    "pet": 100631,
    "acessorios": 100009,
    "informatica": 100644,
    "alimentos": 100629,
    "saude": 100001,
    "suplementos": 100001,
    "esportes": 100637,
    "automotivo": 102187,
    "papelaria": 100638,
    "moda": 100017,
    "audio": 100535,
    "eletrodomesticos": 100010,
    "calcados": 100532,
}

_CAMPOS = (
    "itemId productName price sales ratingStar commissionRate "
    "priceDiscountRate imageUrl offerLink shopName productCatIds"
)


@dataclass
class Idea:
    """Un candidato a grabar, ya con su link monetizado."""

    titulo: str
    precio: Decimal
    ventas: int
    comision_pct: Decimal
    rating: Decimal
    descuento_pct: int
    link: str
    imagen_url: str | None
    puntaje: float


def _normalizar(texto: str) -> str:
    """Sin acentos y en minúsculas, para que 'Calçados' matchee 'calcados'."""
    sin_tildes = unicodedata.normalize("NFKD", texto.strip().lower())
    return "".join(c for c in sin_tildes if not unicodedata.combining(c))


def resolver_categoria(texto: str) -> int | None:
    """ID de categoría si `texto` nombra una, o None (entonces es palabra clave)."""
    return CATEGORIAS.get(_normalizar(texto))


def nombre_categoria(texto: str) -> str | None:
    """Nombre real de la categoría en la que cae `texto`, o None si no es una.

    Sirve para decirle al usuario dónde buscó de verdad: pedir "limpeza" busca en
    toda la categoría Casa e Cozinha, y conviene que lo sepa antes de extrañarse
    de que aparezca una furadeira."""
    cat_id = resolver_categoria(texto)
    return NOMBRES.get(cat_id) if cat_id is not None else None


def puntuar(*, comision_pct: float, ventas: int, rating: float, precio: float) -> float:
    """Puntaje 0..1. Cada factor se normaliza aparte y después se pondera.

    Las ventas van en escala logarítmica porque van de decenas a decenas de miles:
    en escala lineal, un solo éxito masivo aplastaría a todos los demás factores."""
    f_comision = min(comision_pct / _COMISION_TECHO_PCT, 1.0)
    f_ventas = min(math.log10(1 + max(ventas, 0)) / _VENTAS_TECHO_LOG, 1.0)
    # El rating útil vive entre 4 y 5 estrellas; abajo de 4 el factor es 0.
    f_rating = max(0.0, min((rating - 4.0), 1.0))
    if precio <= _PRECIO_IMPULSO:
        f_precio = 1.0
    else:
        f_precio = max(0.0, (_PRECIO_TECHO - precio) / (_PRECIO_TECHO - _PRECIO_IMPULSO))
    return (
        _PESO_COMISION * f_comision
        + _PESO_VENTAS * f_ventas
        + _PESO_RATING * f_rating
        + _PESO_PRECIO * f_precio
    )


def _a_idea(nodo: dict) -> Idea | None:
    try:
        precio = Decimal(str(nodo.get("price") or "0"))
        comision = Decimal(str(nodo.get("commissionRate") or "0")) * 100
        rating = Decimal(str(nodo.get("ratingStar") or "0"))
        ventas = int(nodo.get("sales") or 0)
    except Exception:
        return None
    if not nodo.get("productName") or not nodo.get("offerLink"):
        return None
    return Idea(
        titulo=nodo["productName"],
        precio=precio,
        ventas=ventas,
        comision_pct=comision,
        rating=rating,
        descuento_pct=int(nodo.get("priceDiscountRate") or 0),
        link=nodo["offerLink"],
        imagen_url=nodo.get("imageUrl"),
        puntaje=puntuar(
            comision_pct=float(comision), ventas=ventas,
            rating=float(rating), precio=float(precio),
        ),
    )


def buscar_ideas(
    texto: str,
    app_id: str,
    secret: str,
    *,
    cuantas: int = 5,
    candidatos: int = 40,
    http_post: Callable[..., object] | None = None,
) -> list[Idea]:
    """Top `cuantas` ideas ordenadas por puntaje. Lista vacía ante cualquier fallo.

    Se piden `candidatos` (más de los que se devuelven) porque la API ordena por
    ventas y el reordenamiento por puntaje solo tiene sentido sobre un pozo amplio:
    pedir 5 y reordenar 5 sería reordenar lo que la API ya eligió."""
    cat_id = resolver_categoria(texto)
    if cat_id is not None:
        filtro = f"productCatId:{cat_id}"
    else:
        limpio = texto.replace('"', " ").replace("\\", " ").strip()
        if not limpio:
            return []
        filtro = f'keyword:"{limpio}"'

    query = "{productOfferV2(%s,sortType:2,limit:%d){nodes{%s}}}" % (
        filtro, max(1, min(candidatos, 50)), _CAMPOS,
    )
    kwargs = {"http_post": http_post} if http_post is not None else {}
    data = _graphql_call(app_id, secret, query, **kwargs)
    if not data:
        return []
    nodos = ((data.get("productOfferV2") or {}).get("nodes")) or []
    ideas = [i for i in (_a_idea(n) for n in nodos) if i is not None]
    ideas.sort(key=lambda i: i.puntaje, reverse=True)
    return ideas[:cuantas]
