import re
from decimal import Decimal
from typing import Optional, Tuple

# Frases que marcan un precio "suelto" (sin R$) cuando siguen a un número.
_PRICE_PHRASES = r"à vista|no pix|via pix|em até|parcelado|em \d+x"

# --- Extracción de VALOR (busca en todo el texto) ---
# Descuento con R$: "De R$ 408 por R$ 167"
_DISCOUNT_RS_RE = re.compile(
    r"de\s*r\$\s*([\d.,]+)\s*por\s*r\$\s*([\d.,]+)", re.IGNORECASE
)
# Descuento sin R$ (IAchados): "DE 13,59 | POR 9,16" (pipe opcional).
# \bde\b / \bpor\b evitan matchear "de"/"por" dentro de palabras (ej. "grande").
_DISCOUNT_NORS_RE = re.compile(
    r"\bde\b\s*([\d.,]+)\s*\|?\s*\bpor\b\s*([\d.,]+)", re.IGNORECASE
)
# Precio único con R$: "R$ 19"
_PRICE_RS_RE = re.compile(r"r\$\s*([\d.,]+)", re.IGNORECASE)
# Precio único sin R$ seguido de frase: "69,99 à vista"
_PRICE_PLAIN_RE = re.compile(r"\b(\d[\d.,]*)\s*(?:" + _PRICE_PHRASES + r")", re.IGNORECASE)

# --- Clasificación de LÍNEA (para anclar nombres) ---
_PRICE_RS_LINE_RE = re.compile(r"r\$\s*\d", re.IGNORECASE)
_PRICE_PLAIN_LINE_RE = re.compile(
    r"^\d[\d.,]*\s*(?:" + _PRICE_PHRASES + r")", re.IGNORECASE
)
_POR_LINE_RE = re.compile(r"^por\s*[\d]", re.IGNORECASE)
_COUPON_RE = re.compile(r"%\s*off|off em r\$", re.IGNORECASE)
_LEADING_SYMBOLS_RE = re.compile(r"^[^0-9A-Za-zÀ-ÿ]+")


def parse_br_number(s: str) -> Decimal:
    """Convierte un número brasileño a Decimal. "1.289,10"->1289.10 ; "2.391"->2391."""
    s = s.strip().replace(" ", "").strip(".,")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(".", "")
    return Decimal(s)


def _strip_leading_symbols(line: str) -> str:
    return _LEADING_SYMBOLS_RE.sub("", line)


def is_coupon_line(line: str) -> bool:
    """True si la línea es un cupón / "% OFF" (no un precio de producto)."""
    return bool(_COUPON_RE.search(line or ""))


def is_price_line(line: str) -> bool:
    """True si la línea (ignorando emojis iniciales) expresa un precio de producto.
    Las líneas de cupón/"% OFF" devuelven False para no anclar nombres en posts de cupón."""
    if not line:
        return False
    if is_coupon_line(line):
        return False
    if _PRICE_RS_LINE_RE.search(line):
        return True
    core = _strip_leading_symbols(line).strip()
    if _PRICE_PLAIN_LINE_RE.match(core):
        return True
    if _DISCOUNT_NORS_RE.search(core):   # "DE x | POR y" pair
        return True
    if _POR_LINE_RE.match(core):         # single "POR y ..." line
        return True
    return False


def extract_price(text: Optional[str]) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    """Extrae (precio_final, precio_original) de un texto de oferta.
    Precedencia: descuento con R$ -> descuento sin R$ -> precio único (R$ o frase)."""
    if not text:
        return (None, None)

    m = _DISCOUNT_RS_RE.search(text)
    if m:
        return (parse_br_number(m.group(2)), parse_br_number(m.group(1)))

    m = _DISCOUNT_NORS_RE.search(text)
    if m:
        return (parse_br_number(m.group(2)), parse_br_number(m.group(1)))

    rs_match = _PRICE_RS_RE.search(text)
    plain_match = _PRICE_PLAIN_RE.search(text)
    candidates = [x for x in (rs_match, plain_match) if x is not None]
    if not candidates:
        return (None, None)
    earliest = min(candidates, key=lambda x: x.start())
    return (parse_br_number(earliest.group(1)), None)
