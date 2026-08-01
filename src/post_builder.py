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


def build_price_block(product: Product) -> str:
    """Arma el bloque de precio según la variante del producto."""
    kind = product.price_kind
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
