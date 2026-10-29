"""El "tipo" de un producto, para no repetir el mismo tipo en un dia ni en la semana.

`item_id` solo no alcanza: el mismo tipo llega con muchos item_id y titulos que
arrancan distinto ("Kit", "Maciez", "Marmitas"). Nick se quejo varias veces
(2026-10-20 porta tempero; 2026-10-28 tres cosas de lavadora para Lanny, capinha,
suporte y microfone repetidos para Nick, 3 percarbonatos y 5 potes en WhatsApp).

Lo usan la cola de WhatsApp y el cruce previo a producir videos
(`scripts/video/repetidos.py`). Se agrega una linea por tipo nuevo; lo que no
figura cae a `_firma` (primera palabra significativa del titulo).
"""

from __future__ import annotations

import re

from .product_ideas import _firma, _normalizar

# El orden importa: gana la primera que calza ("capa protetora colchao" es colchon,
# no funda de celular).
_FAMILIAS = {
    "~percarbonato": r"percarbonato|alvejante",
    "~colchao impermeavel": r"(?=.*\bcolchao\b)(?=.*\b(protetor\w*|capa\w*|impermeav\w*)\b)",
    "~pote hermetico": r"\b(potes?|marmitas?|tigelas?|hermetic\w*)\b",
    "~fone": r"\b(fones?|headsets?|earbuds?)\b",
    "~lavadora": r"tanquinho|lavadora|maquina (de )?lavar",
    "~funda celular": r"capinhas?|(?=.*\bcapas?\b)(?=.*\b(celular|iphone)\b)|tempered glass|pelicula",
    "~suporte celular": r"(?=.*\b(suporte|apoio|cordao)\b)(?=.*\b(celular|tablet)\b)",
    "~microfone": r"\bmicrofones?\b",
    "~caixa de som": r"caixa (de )?som|soundbar|alto falante",
    "~top fitness": r"(?=.*\btops?\b)(?=.*\b(fitness|academia|yoga|pilates|treino)\b)",
    "~garrafa termica": r"\bgarrafas?\b",
    "~copo": r"\bcopos?\b",
    "~unhas": r"\bunhas?\b|nail|cuticula",
    "~sandalia": r"sandalias?|papete",
}


def familia(titulo: str) -> str:
    """El tipo de producto: una familia de `_FAMILIAS` o, si ninguna calza, la firma."""
    t = _normalizar(titulo)
    return next((f for f, rx in _FAMILIAS.items() if re.search(rx, t)), _firma(titulo))


def cruzar(candidatos: list[str], historial: list[tuple[float, str, str]], ahora: float,
           dias: int = 7) -> list[tuple[str, list[str]]]:
    """Para cada titulo candidato, lo que ya existe de su mismo tipo.

    `historial` son (ts_epoch, titulo, origen) de UNA cuenta. Un candidato tambien
    choca con otro candidato de la misma lista (dos del mismo tipo en un lote)."""
    desde = ahora - dias * 86400
    vistos: list[tuple[str, str]] = []
    salida = []
    for c in candidatos:
        f = familia(c)
        choques = [f"{o}: {t[:60]}" for ts, t, o in historial if ts >= desde and familia(t) == f]
        choques += [f"este mismo lote: {t[:60]}" for t, ft in vistos if ft == f]
        vistos.append((c, f))
        salida.append((c, choques))
    return salida
