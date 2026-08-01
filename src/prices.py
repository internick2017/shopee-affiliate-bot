import re
from decimal import Decimal

# Frases que marcan un precio "suelto" (sin R$) cuando siguen a un número.
_PRICE_PHRASES = r"à vista|no pix|via pix|em até|parcelado|em \d+x"

# --- Extracción de VALOR (busca en todo el texto) ---
# Descuento con R$: "De R$ 408 por R$ 167"
_DISCOUNT_RS_RE = re.compile(r"de\s*r\$\s*([\d.,]+)\s*por\s*r\$\s*([\d.,]+)", re.IGNORECASE)
# Descuento sin R$ (IAchados): "DE 13,59 | POR 9,16" (pipe opcional).
# \bde\b / \bpor\b evitan matchear "de"/"por" dentro de palabras (ej. "grande").
_DISCOUNT_NORS_RE = re.compile(r"\bde\b\s*([\d.,]+)\s*\|?\s*\bpor\b\s*([\d.,]+)", re.IGNORECASE)
# Precio único con R$: "R$ 19"
_PRICE_RS_RE = re.compile(r"r\$\s*([\d.,]+)", re.IGNORECASE)
# Precio único sin R$ seguido de frase: "69,99 à vista"
_PRICE_PLAIN_RE = re.compile(r"\b(\d[\d.,]*)\s*(?:" + _PRICE_PHRASES + r")", re.IGNORECASE)

# --- Clasificación de LÍNEA (para anclar nombres) ---
_PRICE_RS_LINE_RE = re.compile(r"r\$\s*\d", re.IGNORECASE)
_PRICE_PLAIN_LINE_RE = re.compile(r"^\d[\d.,]*\s*(?:" + _PRICE_PHRASES + r")", re.IGNORECASE)
_POR_LINE_RE = re.compile(r"^por\s*[\d]", re.IGNORECASE)
# "a partir de 28,39 à vista" (Crowman) o "A partir de: R$ 19,99" (Promocasinha):
# el precio más bajo de un producto con variantes.
_A_PARTIR_LINE_RE = re.compile(r"^a partir de:?\s*(?:r\$\s*)?\d", re.IGNORECASE)
_A_PARTIR_RE = re.compile(r"\ba partir de\b", re.IGNORECASE)
# Cupones: "% OFF", "OFF em R$", montos de descuento tipo "cupom de R$10 OFF", y el
# tope de un cupón ("Limite de R$ 50") — ninguno es el precio de un producto.
_COUPON_RE = re.compile(r"%\s*off|off em r\$|r\$\s*\d[\d.,]*\s*off|limite de\s*r\$", re.IGNORECASE)
_LEADING_SYMBOLS_RE = re.compile(r"^[^0-9A-Za-zÀ-ÿ]+")


def parse_br_number(s: str) -> Decimal:
    """Convierte un número brasileño a Decimal. "1.289,10"->1289.10 ; "2.391"->2391."""
    s = s.strip().replace(" ", "").strip(".,")
    if "," in s:
        return Decimal(s.replace(".", "").replace(",", "."))
    if "." in s:
        # Sin coma, el punto es separador de miles solo si agrupa de a tres dígitos
        # ("2.391"). Un grupo final de otro tamaño es un decimal en formato en-US
        # ("99.90"): tratarlo como miles multiplicaría el precio por cien.
        head, _, tail = s.rpartition(".")
        if len(tail) != 3 and "." not in head:
            return Decimal(s)
        return Decimal(s.replace(".", ""))
    return Decimal(s)


def _strip_leading_symbols(line: str) -> str:
    return _LEADING_SYMBOLS_RE.sub("", line)


def is_coupon_line(line: str) -> bool:
    """True si la línea anuncia un cupón / "% OFF" en vez del precio de un producto.

    Un "% off" no basta: Promocasinha escribe "Por: R$ 6,66 (44% off)", donde el
    porcentaje es una insignia detrás del precio. Lo que decide es el orden — si
    el precio viene primero, la línea es un precio; si el "% off" viene primero
    ("10% OFF a partir de R$300"), es un cupón.
    """
    coupon_match = _COUPON_RE.search(line or "")
    if not coupon_match:
        return False
    price_match = _PRICE_RS_LINE_RE.search(line)
    return not (price_match and price_match.start() < coupon_match.start())


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
    if _DISCOUNT_NORS_RE.search(core):  # "DE x | POR y" pair
        return True
    if _POR_LINE_RE.match(core):  # single "POR y ..." line
        return True
    return bool(_A_PARTIR_LINE_RE.match(core))  # "a partir de 28,39 à vista"


def extract_price(text: str | None) -> tuple[Decimal | None, Decimal | None]:
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


def price_start(line: str | None) -> int | None:
    """Índice donde arranca la expresión de precio dentro de la línea, o None.

    Sirve para recortar el nombre que la precede: en "🔹 The Last of Us - R$ 49" el
    producto está en la propia línea de precio. Usa la misma precedencia que
    `extract_price`, así que no confunde el "12" de "Kit 12 Cuecas" con el precio.
    """
    if not line or is_coupon_line(line):
        return None
    for pattern in (_DISCOUNT_RS_RE, _DISCOUNT_NORS_RE):
        m = pattern.search(line)
        if m:
            return m.start()
    starts = [m.start() for m in (_PRICE_RS_RE.search(line), _PRICE_PLAIN_RE.search(line)) if m]
    return min(starts) if starts else None


def extract_price_info(line: str | None):
    """Como `extract_price`, pero pensado para UNA línea y con la variante de precio:
    devuelve `(final, original, es_rango)`.

    "Es rango" = la línea dice "a partir de", o sea que el precio es el más bajo de
    varias variantes. El post lo anuncia como "A partir de ..." en vez de "Por: ...".
    Una línea de cupón no tiene precio: devuelve `(None, None, False)`.
    """
    if not line or is_coupon_line(line):
        return (None, None, False)
    final, original = extract_price(line)
    if final is None:
        return (None, None, False)
    # Un descuento ("De X por Y") ya es explícito; "a partir de" solo marca rango
    # cuando es el único precio de la línea.
    is_range = original is None and bool(_A_PARTIR_RE.search(line))
    return (final, original, is_range)
