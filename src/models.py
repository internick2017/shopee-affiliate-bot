from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class Product:
    """Datos de un producto de Shopee necesarios para armar un post."""

    item_id: int
    shop_id: int
    name: str
    price_final: Decimal
    image_url: str
    price_original: Optional[Decimal] = None
    is_price_range: bool = False
    affiliate_link: str = ""

    @property
    def price_kind(self) -> str:
        """Decide qué variante de bloque de precio usar.

        - "range":   producto con variantes -> "A partir de ..."
        - "discount": hay precio original mayor -> "De: ... Por: ..."
        - "plain":   solo precio final -> "Por: ..."
        """
        if self.is_price_range:
            return "range"
        if self.price_original is not None and self.price_original > self.price_final:
            return "discount"
        return "plain"
