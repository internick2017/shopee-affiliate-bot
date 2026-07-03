from decimal import Decimal
from typing import Optional, Protocol

from .models import Product


class ShopeeClient(Protocol):
    """Interfaz que el orquestador consume. La implementación real llega en Fase 3."""

    def fetch(self, shop_id: int, item_id: int) -> Product:
        ...


class MockShopeeClient:
    """Cliente falso para Fases 1-2: devuelve datos de prueba sin tocar la red."""

    def __init__(self, product: Optional[Product] = None):
        self._product = product

    def fetch(self, shop_id: int, item_id: int) -> Product:
        if self._product is not None:
            return self._product
        return Product(
            item_id=item_id,
            shop_id=shop_id,
            name="Produto de Teste Shopee",
            price_final=Decimal("16.90"),
            price_original=Decimal("35.00"),
            image_url="https://cf.shopee.com.br/file/mock-image",
            is_price_range=False,
            affiliate_link=f"https://s.shopee.com.br/mock{item_id}",
        )


class RealShopeeClient:
    """Cliente real de la Shopee Affiliate Open API. IMPLEMENTAR EN FASE 3.

    Endpoint: POST https://open-api.affiliate.shopee.com.br/graphql
    Auth header: Authorization con firma SHA256(AppId + Timestamp + Payload + Secret).

    `fetch` debe:
      1. Consultar los datos del producto por (shop_id, item_id) — nombre,
         precio final, precio original (si hay), imagen, y si tiene rango de
         precio (variantes) para setear is_price_range.
      2. Generar el shortlink de afiliada de Lanny para la URL del producto.
      3. Devolver un Product completo (con affiliate_link).

    Query GraphQL previsto (verificar campos contra la doc real con credenciales):
      productOfferV2(itemId: <item_id>, shopId: <shop_id>) {
        nodes { itemId shopId productName priceMin priceMax price
                priceDiscountRate imageUrl }
      }
      generateShortLink(input: {originUrl: "<product_url>", subIds: [...]}) {
        shortLink
      }

    Plan B si la API no permite consulta puntual por itemId: tomar nombre y
    precio del mensaje original de Telegram y usar la API solo para
    generateShortLink. Este cambio queda aislado dentro de esta clase.
    """

    def __init__(
        self,
        app_id: str,
        secret: str,
        base_url: str = "https://open-api.affiliate.shopee.com.br/graphql",
    ):
        self._app_id = app_id
        self._secret = secret
        self._base_url = base_url

    def fetch(self, shop_id: int, item_id: int) -> Product:
        raise NotImplementedError(
            "RealShopeeClient.fetch: implementar en Fase 3 con las credenciales "
            "de Shopee. Ver el docstring de la clase para el query GraphQL."
        )
