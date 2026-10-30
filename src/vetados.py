"""Productos que nunca se publican: alcohol, cigarrillo y armas (regla de Nick, 2026-10-30).

No es politica de Shopee: pertenecen a una iglesia y no publican lo que no harian. Se mira
el titulo sin acentos y por palabra entera, para no vetar "Armazenamento" ni "Armaf".
Se veta la bebida, no el utensilio: un vaso "para cerveja" depende de como se use (Nick).
"""

from __future__ import annotations

import re
import unicodedata

_BEBIDA = re.compile(
    r"\b(cervej\w*|chopp?|chopeira|vinhos?|vinicol\w*|whisk\w*|uisque|vodka|tequila|gin|licor\w*"
    r"|cachaca\w*|caipirinha\w*|champanhe\w*|espumante\w*|bebidas? alcoolica\w*|alcoolica\w*)\b"
)
_UTENSILIO = re.compile(
    r"\b(copos?|tacas?|canecas?|jarras?|baldes?|coolers?|abridor\w*|saca.?rolhas|termic\w*)\b"
)
_SIEMPRE = re.compile(
    r"\b(cigarr\w*|tabaco|charuto\w*|narguil\w*|vape\w*|vaper|pod descartavel|isqueiro\w*"
    r"|armas?|arminha\w*|espingarda\w*|revolver\w*|airsoft|paintball|municao|cartucho de bala"
    r"|canivete\w*|soco ingles|taser|pistolas? (?:de )?(?:brinquedo|airsoft|gel|pressao|bolinha))\b"
)


def vetado(titulo: str) -> bool:
    t = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode().lower()
    return bool(_SIEMPRE.search(t) or (_BEBIDA.search(t) and not _UTENSILIO.search(t)))
