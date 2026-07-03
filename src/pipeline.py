import logging
from typing import Callable, List, Optional, Tuple

from .post_builder import build_post

logger = logging.getLogger(__name__)


class Pipeline:
    """Conecta las piezas: extrae link -> resuelve -> dedup -> Shopee -> arma -> postea."""

    def __init__(self, extractor, resolver, dedup, client, hookbank, poster):
        self._extractor: Callable[[Optional[str]], List[str]] = extractor
        self._resolver: Callable[[str], Tuple[int, int]] = resolver
        self._dedup = dedup
        self._client = client
        self._hookbank = hookbank
        self._poster = poster

    async def handle(self, text: str, chat_title: Optional[str] = None) -> int:
        posted = 0
        for link in self._extractor(text):
            try:
                shop_id, item_id = self._resolver(link)
            except Exception as exc:
                logger.info("No se pudo resolver el link: %s (%s)", link, exc)
                continue

            if self._dedup.seen(item_id):
                logger.info("Producto ya posteado, se saltea: %s", item_id)
                continue

            try:
                product = self._client.fetch(shop_id, item_id)
            except NotImplementedError:
                logger.warning(
                    "Cliente Shopee real no implementado (Fase 3). Se saltea %s.",
                    item_id,
                )
                continue
            except Exception as exc:  # datos de un producto no deben tumbar el bot
                logger.error("Error al traer producto %s: %s", item_id, exc)
                continue

            hook = self._hookbank.next()
            post_text = build_post(product, hook)
            await self._poster.post(product.image_url, post_text)
            self._dedup.mark(item_id)
            posted += 1
            logger.info("Post publicado para el producto %s", item_id)
        return posted
