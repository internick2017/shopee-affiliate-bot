import re

from .prices import is_price_line as _is_price_line

_ANUNCIO_RE = re.compile(r"^an[uú]ncio$", re.IGNORECASE)
_OFERTA_RE = re.compile(
    r"oferta exclusiva|oferta v[aá]lida|exclusivo para membros|exclusiva para membros|membros prime",
    re.IGNORECASE,
)
_CUPOM_RE = re.compile(r"cupom|cupons", re.IGNORECASE)
_OFF_RE = re.compile(r"%\s*off|off em r\$", re.IGNORECASE)

# Strips leading emojis/symbols (anything that isn't a digit, ASCII letter,
# or accented Latin letter) while preserving leading digits/letters.
_LEADING_SYMBOLS_RE = re.compile(r"^[^0-9A-Za-zÀ-ÿ]+")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_leading_symbols(line: str) -> str:
    return _LEADING_SYMBOLS_RE.sub("", line)


def _is_noise_line(line: str) -> bool:
    if not line:
        return True
    if _is_price_line(line):
        return True
    if "http" in line:
        return True
    if "Grupos de promos" in line:
        return True

    core = _strip_leading_symbols(line).strip()

    if _ANUNCIO_RE.match(core):
        return True
    if core.startswith("Vendido por") or "Loja Oficial" in line:
        return True
    if _CUPOM_RE.search(line):
        return True
    if (
        core.startswith("Use o Cupom")
        or core.startswith("Resgate")
        or core.startswith("Ative aqui")
        or core.startswith("Selecione")
    ):
        return True
    if line.startswith("-"):
        return True
    if _OFERTA_RE.search(line):
        return True
    return bool(_OFF_RE.search(line))


def _clean_candidate(line: str) -> str:
    cleaned = _LEADING_SYMBOLS_RE.sub("", line)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned)
    return cleaned.strip()


def _is_coupon_announcement(cleaned: str) -> bool:
    lower = cleaned.lower()
    return (
        "cupom" in lower
        or "cupons" in lower
        or "% off" in lower
        or "off em r$" in lower
    )


def extract_product_names(text: str | None) -> list[str]:
    """Extrai candidatos de nome de produto de uma mensagem de promo bruta.

    Para cada linha de PREÇO (em ordem no documento), o candidato é a linha
    não-ruído mais próxima acima dela. Mensagens somente de cupom (sem preço
    ancorado a um nome de produto válido) retornam lista vazia.
    """
    if not text:
        return []

    lines = [line.strip() for line in text.split("\n")]

    candidates: list[str] = []
    seen = set()

    for i, line in enumerate(lines):
        if not _is_price_line(line):
            continue

        candidate_line = None
        j = i - 1
        while j >= 0:
            if not _is_noise_line(lines[j]):
                candidate_line = lines[j]
                break
            j -= 1

        if candidate_line is None:
            continue

        cleaned = _clean_candidate(candidate_line)
        if not cleaned or _is_coupon_announcement(cleaned):
            continue
        if cleaned in seen:
            continue

        seen.add(cleaned)
        candidates.append(cleaned)

    return candidates
