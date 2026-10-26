"""Link de afiliado de Magazine Luiza (programa Influenciador Magalu).

No hay API ni app oficial, y Magalu bloquea la automatización (403) y el contrato
prohíbe robots (cláusula 10.5). El link se arma solo como texto, sin consultar a
Magalu: alcanza con la tienda y el código del producto (`/<tienda>/p/<código>/`,
probado a mano el 2026-10-26; Magalu completa el resto, vendedor incluido).
"""

import re
from urllib.parse import urlsplit

# La única cuenta de Magalu, a nombre de Setup Justo; se usa en todos los canales.
# Magalu redirige `/magazinesetupjusto/` a `/setupjusto/`: se usa el corto directo.
MAGALU_LOJA = "setupjusto"

_HOSTS_MAGALU = {"magazineluiza.com.br", "www.magazineluiza.com.br", "m.magazineluiza.com.br"}
_HOSTS_VOCE = {"magazinevoce.com.br", "www.magazinevoce.com.br"}
# shortcut: no verificado con una venta real que este formato atribuya; confirmarlo
# con la primera venta en el panel antes de pasar Magalu a verde.
_PRODUTO_RE = re.compile(r"^/[^/]+/p/([0-9a-z]+)/")


def link_afiliado_magalu(url: str, loja: str = MAGALU_LOJA) -> str | None:
    """Convierte un link de producto de Magalu al de la tienda `loja`.

    Acepta magazineluiza.com.br (www, m. o pelado) y magazinevoce.com.br de cualquier
    tienda. Descarta query y fragmento. Devuelve None si no es un producto de Magalu.
    """
    parts = urlsplit(url or "")
    host = parts.netloc.lower()
    path = parts.path
    if host in _HOSTS_VOCE:
        # /<otra-tienda>/<slug>/p/<id>/... -> sacar la tienda de adelante
        path = "/" + path.lstrip("/").partition("/")[2]
    elif host not in _HOSTS_MAGALU:
        return None
    match = _PRODUTO_RE.match(path)
    if not match:
        return None
    return f"https://www.magazinevoce.com.br/{loja}/p/{match.group(1)}/"
