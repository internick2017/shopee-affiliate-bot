import logging

logger = logging.getLogger(__name__)


class OfferPipeline:
    """Router: le ofrece el mensaje a cada handler, y cada uno atiende la parte que le
    toca. Devuelve cuántas ofertas se publicaron en total (0 = nadie lo quiso).

    No es "gana el primero": un mensaje puede traer productos de varias plataformas
    (Crowman postea un bloque de Amazon y otro de Mercado Livre en el mismo mensaje),
    y si el primer handler se lo quedara entero, los demás productos se perderían.
    Los handlers no se pisan porque cada uno reclama por su propio dominio de links.

    Un handler que falla no le roba el mensaje a los siguientes.
    """

    def __init__(self, handlers):
        self._handlers = list(handlers)

    async def handle(self, text, chat_title=None, photo=None) -> int:
        total = 0
        for handler in self._handlers:
            try:
                total += await handler.handle(text, chat_title, photo=photo)
            except Exception:
                logger.exception(
                    "Handler %s falló procesando un mensaje; se prueba el siguiente",
                    type(handler).__name__,
                )
        return total
