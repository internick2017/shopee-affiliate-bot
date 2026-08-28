from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Product:
    """Datos de un producto de Shopee necesarios para armar un post."""

    item_id: int
    shop_id: int
    name: str
    price_final: Decimal
    image_url: str
    price_original: Decimal | None = None
    is_price_range: bool = False
    affiliate_link: str = ""

    @property
    def price_kind(self) -> str:
        """Decide qué variante de bloque de precio usar.

        - "discount_range": descuento Y variantes -> "De: ... A partir de: ..."
        - "range":   producto con variantes -> "A partir de ..."
        - "discount": hay precio original mayor -> "De: ... Por: ..."
        - "plain":   solo precio final -> "Por: ..."
        """
        # El orden importa: un producto puede tener las dos cosas a la vez (64 de 200
        # productos de Shopee medidos). Quedarse solo con el rango borraria el
        # "De/Por", que es el gancho del post.
        hay_descuento = self.price_original is not None and self.price_original > self.price_final
        if self.is_price_range and hay_descuento:
            return "discount_range"
        if self.is_price_range:
            return "range"
        if hay_descuento:
            return "discount"
        return "plain"
