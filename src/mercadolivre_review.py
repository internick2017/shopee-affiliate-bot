"""Handler de Mercado Livre: si el link `meli.la` resuelve a un producto puntual,
arma el post con el link propio de Nick (automático). Si no, reenvía la oferta al
canal para armar el link a mano.

Los tres canales fuente postean shortlinks `meli.la/XXXX` que redirigen a
`mercadolivre.com.br/social/<afiliado>?ref=<blob>`: el `ref` va cifrado y firmado a
la cuenta que lo generó, así que no se puede reescribir. Pero la página resuelta
trae embebido el item_id real del producto (ver `mercadolivre_resolver.py`), y con
eso alcanza para armar el link propio sin pasar por la Central de Afiliados. Cuando
el link es de tipo "lista" (sin item_id resoluble), no hay nada que automatizar: se
sigue reenviando marcado para que Nick lo genere a mano.
"""
import asyncio
import logging
import re
from collections.abc import Callable

from .links import MERCADOLIVRE_LINK_RE, foreign_link_res
from .mercadolivre_resolver import (
    MercadoLivreOffer,
    build_own_mercadolivre_links,
    extract_meli_shortlinks,
    has_meli_shortlinks,
    resolve_mercadolivre_offer,
    retag_mercadolivre_url,
)
from .models import Product
from .post_builder import build_post
from .posting import post_offer
from .review_forward import (
    FOOTER_MARKERS,
    ReviewPipeline,
    build_review_message,
    drop_foreign_blocks,
    has_links,
    review_dedup_key,
)

logger = logging.getLogger(__name__)

_MERCADOLIVRE_RE = MERCADOLIVRE_LINK_RE
PLATFORM = "ml"

DEFAULT_MARKER = "⚠️ MERCADO LIVRE: gerar link de afiliado e postar manual"

# El código va tras la palabra "cupom", con o sin ":" y con hasta 30 caracteres en el
# medio ("CUPOM Exclusivo Amazon Prime: XXX"). Piezas del patrón, cada una corrigiendo
# un fallo real encontrado al probarlo contra los 600 mensajes de la medición:
#   - `(?i:cupom)`: solo la palabra "cupom" es case-insensitive (las fuentes escriben
#     "CUPOM", "Cupom", "cupom" sin criterio). El resto del patrón NO hereda ese flag.
#   - `\b(...)`: word boundary ANTES del grupo de captura. Sin esto, el relleno
#     `[^\n:]{0,30}` (greedy) puede backtrackear hasta la mitad de una palabra y
#     capturar un sufijo — "MODA" en vez de "MELIMODA", "ADOS" en vez de
#     "SELECIONADOS" — que se cuela porque el sufijo no está en la lista de
#     stopwords aunque la palabra completa sí.
#   - `(?=[A-Z0-9]*[A-Z])`: exige al menos UNA letra en el token. Sin esto,
#     `[A-Z0-9]{4,25}` a secas matchea números sueltos de 4+ dígitos — un año como
#     "2026" cerca de la palabra "cupom" se leería como código.
#   - El código puede EMPEZAR con dígito ("15ACESS" es un cupón real de Promocasinha),
#     por eso `[A-Z0-9]{4,25}` y no `[A-Z][A-Z0-9]{3,24}`.
_CUPON_RE = re.compile(
    r"(?i:cupom)\b[^\n:]{0,30}:?\s*\b(?=[A-Z0-9]*[A-Z])([A-Z0-9]{4,25})\b"
)

# Palabras que siguen a "cupom" en frases sueltas y NO son códigos. Salieron de medir
# 600 mensajes reales de los 3 canales fuente el 2026-07-18: sin este filtro se
# publicaba "CUPOM: MERCADO" o "CUPOM: SELECIONADOS", que no sirven de nada.
_CUPON_STOPWORDS = frozenset({
    "MERCADO", "LIVRE", "LOJA", "SELECIONADOS", "ESGOTADO", "LIMITADO", "SHOPEE",
    "AMAZON", "PRODUTOS", "DESCONTO", "DESCONTOS", "EXCLUSIVO", "EXCLUSIVA", "PRIME",
    "COMPRAS", "PIX", "FRETE", "GRATIS", "OFERTA", "OFERTAS", "PROMO", "VALIDO",
})

# Un cupón con la marca de un canal fuente puede ser de SU programa de afiliados: la
# ayuda oficial de ML (mercadolivre.com.br/ajuda/35616) confirma que existen cupones
# de afiliado, y activarlos manda al comprador al buscador de ML, fuera de nuestro
# link. Los cupones de campaña de ML que SÍ circulan en las fuentes (SEMPRENAMODA,
# MELIMODA) no llevan marca de nadie — verificado el 2026-07-18: los mismos códigos
# aparecen en canales que compiten entre sí, lo que descarta que sean exclusivos.
_MARCAS_FUENTE = ("IACHADOS", "CROWMAN", "PROMOCASINHA", "ACHADOS", "CASINHA")


def has_mercadolivre_links(text: str | None) -> bool:
    """True si el texto contiene al menos un link de Mercado Livre."""
    return has_links(text, _MERCADOLIVRE_RE)


def extract_cupon(text: str | None) -> str | None:
    """El código de cupón del mensaje original, o None si no hay uno confiable."""
    if not text:
        return None
    for match in _CUPON_RE.finditer(text):
        codigo = match.group(1).upper()
        if codigo in _CUPON_STOPWORDS:
            continue
        if any(marca in codigo for marca in _MARCAS_FUENTE):
            continue
        return codigo
    return None


def build_mercadolivre_review_message(
    text: str | None, marker: str = DEFAULT_MARKER
) -> str | None:
    """Marca + texto original sin el footer del competidor ni los productos de otras
    plataformas. None si no hay ML."""
    return build_review_message(text, _MERCADOLIVRE_RE, marker, platform=PLATFORM)


def mercadolivre_dedup_key(text: str | None) -> str | None:
    return review_dedup_key(text, _MERCADOLIVRE_RE, PLATFORM)


def _build_post_propio(
    text: str, offer: MercadoLivreOffer, matt_word: str, matt_tool: str, hook: str
) -> str:
    """El post con el template de Lanny y los datos que ML informa AHORA."""
    extras: list[str] = []
    if offer.descuento:
        extras.append(f"🏷️ {offer.descuento}")
    cupon = extract_cupon(text)
    if cupon:
        extras.append(f"🎟️ CUPOM: {cupon}")

    producto = Product(
        item_id=0,
        shop_id=0,
        name=offer.titulo,
        price_final=offer.precio,
        image_url="",
        price_original=offer.precio_previo,
        affiliate_link=retag_mercadolivre_url(
            offer.url_canonica, matt_word, matt_tool
        ),
    )
    return build_post(producto, hook, extra_lines=tuple(extras))


def build_mercadolivre_auto_post(
    text: str | None,
    matt_word: str,
    matt_tool: str,
    *,
    hook: str | None = None,
    http_get: Callable[..., object] | None = None,
) -> str | None:
    """Arma el post YA MONETIZADO de Mercado Livre.

    Con `hook`: intenta el post propio (template de Lanny + datos reales de ML). Si el
    mensaje no trae exactamente un producto, si ML no resuelve, o si no hay descuento
    comprobable, devuelve None directo — el caller cae al reenvío marcado, sin pasar por
    el camino viejo de abajo.

    Sin `hook` (compat con el comportamiento anterior a este cambio): reemplaza cada
    shortlink por el link propio en el texto de la fuente, todo-o-nada. None si no hay
    shortlinks resolubles o si ALGUNO no resolvió.
    """
    resolve_kwargs = {} if http_get is None else {"http_get": http_get}

    if hook is not None:
        if not text:
            return None
        enlaces = extract_meli_shortlinks(text)
        # Un solo producto por post: con varios shortlinks no se sabe cuál es el del
        # mensaje, así que no se arma nada en vez de adivinar.
        if len(enlaces) != 1:
            return None
        offer = resolve_mercadolivre_offer(enlaces[0], **resolve_kwargs)
        if not offer or not offer.tiene_descuento:
            return None
        return _build_post_propio(text, offer, matt_word, matt_tool, hook)

    resolved = build_own_mercadolivre_links(text, matt_word, matt_tool, **resolve_kwargs)
    if not resolved:
        return None

    assert text is not None
    result = text
    for shortlink, own_link in resolved.items():
        result = result.replace(shortlink, own_link)

    filtered = "\n".join(
        line
        for line in result.split("\n")
        if not any(marker in line.lower() for marker in FOOTER_MARKERS)
    )
    filtered = drop_foreign_blocks(filtered, _MERCADOLIVRE_RE, foreign_link_res(PLATFORM))
    return filtered.strip()


class MercadoLivreReviewPipeline(ReviewPipeline):
    """Intenta el post automático (ver build_mercadolivre_auto_post); si no se puede,
    cae al reenvío manual de siempre (comportamiento heredado de ReviewPipeline)."""

    def __init__(
        self,
        poster,
        marker: str = DEFAULT_MARKER,
        dedup=None,
        matt_word: str | None = None,
        matt_tool: str | None = None,
        hooks=None,
    ):
        super().__init__(
            poster,
            link_re=_MERCADOLIVRE_RE,
            marker=marker,
            prefix=PLATFORM,
            platform="Mercado Livre",
            dedup=dedup,
        )
        self._matt_word = matt_word
        self._matt_tool = matt_tool
        self._hooks = hooks

    async def handle(self, text, chat_title=None, photo=None) -> int:
        # Igual que AmazonPipeline._expanded: solo se spawnea el thread de resolución
        # HTTP si el mensaje efectivamente trae shortlinks de ML. El resto (Amazon,
        # Shopee puros) no paga ese costo.
        if self._matt_word and self._matt_tool and has_meli_shortlinks(text):
            auto_msg = await asyncio.to_thread(
                build_mercadolivre_auto_post,
                text,
                self._matt_word,
                self._matt_tool,
                hook=self._hooks.next() if self._hooks else None,
            )
            if auto_msg:
                key = self.dedup_key(text)
                if key and self._dedup and not self._dedup.claim(key):
                    logger.info(
                        "Oferta de Mercado Livre ya publicada (%s); se omite", key
                    )
                    return 1
                try:
                    await post_offer(self._poster, auto_msg, photo)
                except Exception:
                    if key and self._dedup:
                        self._dedup.release(key)
                    raise
                logger.info("Oferta de Mercado Livre auto-monetizada y publicada")
                return 1

        return await super().handle(text, chat_title, photo=photo)
