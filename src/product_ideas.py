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

# Peso de cada factor. El principal es el RETORNO (reales por venta), no la
# comisión en porcentaje: un 30% sobre R$8 deja menos que un 12% sobre R$60, y la
# version anterior de esta formula no lo veia porque miraba el porcentaje suelto.
#
# Medido sobre las ventas reales de Nick (90 dias, 73 items completados): la
# comision por venta sube con el precio — R$1,48 por item hasta R$20, R$3,35 entre
# R$20 y R$50, R$5,17 entre R$50 y R$80, R$14,67 arriba de R$150. Los items de
# R$80+ son el 8% de las ventas pero el 24% de la comision.
#
# OJO con esa medicion: tiene sesgo de seleccion. El canal postea sobre todo
# productos baratos, asi que la muestra esta cargada de baratos. Dice que un caro
# PAGA mas cuando se vende, no que convierta mas seguido. Por eso el precio sigue
# teniendo una preferencia por lo barato, pero suave: la version anterior ponia
# CERO arriba de R$80 y borraba de plano la banda mas rentable.
_PESO_RETORNO = 0.35
_PESO_VENTAS = 0.30
_PESO_PRECIO = 0.20
_PESO_RATING = 0.15

_RETORNO_TECHO = 8.0         # R$ por venta; la mediana real de Nick es R$2,07
_VENTAS_TECHO_LOG = 5.0      # log10(100000): 100k ventas satura el factor
_PRECIO_IMPULSO = 30.0       # hasta acá, compra por impulso plena
_PRECIO_CARO = 150.0         # de acá en adelante el factor no baja más
_PRECIO_PISO = 0.35          # nunca 0: un caro rentable no debe quedar descartado

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
    # Verificadas en una segunda pasada (2026-08-28) mirando que trae cada una:
    # eran las de muestra chica en el sampleo inicial, no las obvias.
    100016: "Bolsas Femininas",
    100533: "Mochilas e Carteiras",
    100534: "Relógios",
    100633: "Moda Infantil",
    100012: "Chinelos e Palmilhas",
    100015: "Malas e Viagem",
    100643: "Livros",
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
    "bolsas": 100016,
    "mochilas": 100533,
    "carteiras": 100533,
    "relogios": 100534,
    "infantil": 100633,
    "criancas": 100633,
    "chinelos": 100012,
    "palmilhas": 100012,
    "viagem": 100015,
    "malas": 100015,
    "livros": 100643,
}

_CAMPOS = (
    "itemId productName price sales ratingStar commissionRate "
    "priceDiscountRate imageUrl offerLink shopName productCatIds"
)


@dataclass
class Idea:
    """Un candidato a grabar, ya con su link monetizado."""

    item_id: int
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


def retorno_por_venta(precio: float, comision_pct: float) -> float:
    """Reales que deja cada venta. Es lo que realmente entra al bolsillo, y por eso
    reemplaza al porcentaje de comision suelto como factor principal."""
    return max(0.0, precio) * max(0.0, comision_pct) / 100


def puntuar(*, comision_pct: float, ventas: int, rating: float, precio: float) -> float:
    """Puntaje 0..1. Cada factor se normaliza aparte y después se pondera.

    Las ventas van en escala logarítmica porque van de decenas a decenas de miles:
    en escala lineal, un solo éxito masivo aplastaría a todos los demás factores."""
    f_retorno = min(retorno_por_venta(precio, comision_pct) / _RETORNO_TECHO, 1.0)
    f_ventas = min(math.log10(1 + max(ventas, 0)) / _VENTAS_TECHO_LOG, 1.0)
    # El rating útil vive entre 4 y 5 estrellas; abajo de 4 el factor es 0.
    f_rating = max(0.0, min((rating - 4.0), 1.0))
    # Preferencia por lo barato, pero con piso: los caros pagan mejor por venta y
    # descartarlos de plano fue el error de la version anterior.
    if precio <= _PRECIO_IMPULSO:
        f_precio = 1.0
    elif precio >= _PRECIO_CARO:
        f_precio = _PRECIO_PISO
    else:
        avance = (precio - _PRECIO_IMPULSO) / (_PRECIO_CARO - _PRECIO_IMPULSO)
        f_precio = 1.0 - avance * (1.0 - _PRECIO_PISO)
    return (
        _PESO_RETORNO * f_retorno
        + _PESO_VENTAS * f_ventas
        + _PESO_RATING * f_rating
        + _PESO_PRECIO * f_precio
    )


# Palabras que aparecen en casi cualquier titulo y no distinguen un producto de
# otro: si entraran en la firma, dos productos distintos pareceran el mismo.
_RUIDO = {
    "kit", "de", "da", "do", "para", "com", "sem", "e", "em", "a", "o", "os", "as",
    "un", "uma", "por", "pcs", "pecas", "unidades", "und", "un", "novo", "nova",
    "original", "premium", "profissional", "top", "promocao", "frete", "gratis",
}


def _firma(titulo: str) -> str:
    """Identidad aproximada de un producto, para no ofrecer cinco veces lo mismo.

    Es la PRIMERA palabra significativa del titulo. En Shopee los titulos arrancan
    por el tipo de producto y siguen con adjetivos y medidas, asi que esa palabra
    sola alcanza para agrupar variantes: "Percarbonato 100% Puro Tira Manchas..."
    y "Percarbonato de Sodio 100% Puro Limpeza..." comparten firma.

    Con dos palabras NO funcionaba: esos dos daban "percarbonato puro" y
    "percarbonato sodio", firmas distintas para el mismo producto. Una sola palabra
    agrupa de mas en algun caso (dos limpiadores distintos comparten "limpador"),
    pero para VARIEDAD agrupar de mas es el error barato."""
    palabras = []
    for bruta in _normalizar(titulo).replace("/", " ").replace("-", " ").split():
        limpia = "".join(c for c in bruta if c.isalpha())
        if len(limpia) >= 3 and limpia not in _RUIDO:
            palabras.append(limpia)
        if palabras:
            break
    return " ".join(palabras) or _normalizar(titulo)[:12]


def _variar(ideas: list["Idea"], cuantas: int) -> list["Idea"]:
    """Toma las mejores `cuantas` evitando repetir el mismo producto.

    Recorre en orden de puntaje y saltea las firmas ya vistas. Si con eso no
    alcanza, completa con las mejores descartadas: es preferible devolver algo
    parecido a devolver menos de lo pedido."""
    elegidas, vistas, sobrantes = [], set(), []
    for idea in ideas:
        f = _firma(idea.titulo)
        if f in vistas:
            sobrantes.append(idea)
            continue
        vistas.add(f)
        elegidas.append(idea)
        if len(elegidas) == cuantas:
            return elegidas
    return (elegidas + sobrantes)[:cuantas]


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
    try:
        item_id = int(nodo.get("itemId"))
    except (TypeError, ValueError):
        return None
    return Idea(
        item_id=item_id,
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
    excluir: set[int] | None = None,
    http_post: Callable[..., object] | None = None,
) -> list[Idea]:
    """Top `cuantas` ideas ordenadas por puntaje. Lista vacía ante cualquier fallo.

    `excluir`: item_ids a descartar (los ya grabados). Se filtra ANTES de aplicar
    la variedad, para que un producto descartado no gaste el cupo de su firma y
    deje afuera a otro parecido que si sirve.

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
    if excluir:
        ideas = [i for i in ideas if i.item_id not in excluir]
    ideas.sort(key=lambda i: i.puntaje, reverse=True)
    return _variar(ideas, cuantas)
