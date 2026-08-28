import random
from decimal import Decimal
from pathlib import Path

from .models import Product


def format_brl(value: Decimal) -> str:
    """Formatea un Decimal como precio brasileño: Decimal('1234.5') -> 'R$ 1.234,50'."""
    quantized = value.quantize(Decimal("0.01"))
    integer_part, frac_part = f"{quantized:.2f}".split(".")
    integer_with_dots = f"{int(integer_part):,}".replace(",", ".")
    return f"R$ {integer_with_dots},{frac_part}"


# Desde cuántas veces el precio mínimo se considera que el producto "tiene
# variaciones" y hay que decir "A partir de". Medido sobre 300 productos reales
# (2026-08-28): el 54% tiene algún rango, pero avisar por centavos seria ruido.
_RANGO_RELEVANTE = Decimal("1.5")


def rango_relevante(minimo, maximo) -> bool:
    """¿El máximo está lo bastante lejos del mínimo como para aclararlo?

    Vive acá, al lado de `format_brl`, porque el mismo corte lo usan el post que se
    publica y el aviso que recibe Lanny: si se separaran, el bot avisaria de un
    rango que el post no reconoce (o al revés).
    """
    try:
        lo, hi = Decimal(str(minimo)), Decimal(str(maximo))
    except (TypeError, ValueError, ArithmeticError):
        return False
    return lo > 0 and hi >= lo * _RANGO_RELEVANTE


def build_price_block(product: Product) -> str:
    """Arma el bloque de precio según la variante del producto."""
    kind = product.price_kind
    if kind == "discount_range":
        assert product.price_original is not None
        return (
            f"❌ De: {format_brl(product.price_original)}\n"
            f"✅ A partir de: {format_brl(product.price_final)} 😱🛒"
        )
    if kind == "range":
        return f"✅ A partir de {format_brl(product.price_final)} 😱🛒"
    if kind == "discount":
        assert product.price_original is not None
        return (
            f"❌ De: {format_brl(product.price_original)}\n"
            f"✅ Por: {format_brl(product.price_final)} 😱🛒"
        )
    return f"✅ Por: {format_brl(product.price_final)} 😱🛒"


def build_post(product: Product, hook: str, extra_lines: tuple[str, ...] = ()) -> str:
    """Arma el texto final del post con el estilo de Lanny.

    `extra_lines` cuelga del bloque de precio y existe para Mercado Livre, que suma la
    etiqueta de descuento y el cupón. Amazon no las usa: sin extras el post es idéntico
    al de siempre, así el template sigue siendo uno solo para las dos plataformas.
    """
    price_block = build_price_block(product)
    if extra_lines:
        price_block += "\n" + "\n".join(extra_lines)
    return (
        f"{hook}\n\n"
        f"🛍️ {product.name}\n\n"
        f"{price_block}\n\n"
        f"🛒 Compre aqui: {product.affiliate_link}\n\n"
        f"⚠️ Promoção sujeita a alteração a qualquer momento."
    )


class HookBank:
    """Banco de ganchos rotativos. Elige uno al azar sin repetir el último."""

    def __init__(self, hooks: list[str]):
        if not hooks:
            raise ValueError("El banco de ganchos está vacío.")
        self._hooks = list(hooks)
        self._last: str | None = None

    @classmethod
    def from_file(cls, path: str | Path) -> "HookBank":
        lines = [
            line.strip()
            for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return cls(lines)

    def next(self) -> str:
        candidates = [h for h in self._hooks if h != self._last] or self._hooks
        choice = random.choice(candidates)
        self._last = choice
        return choice
