import logging

logger = logging.getLogger(__name__)


class OfferPipeline:
    """Router: recorre una lista ordenada de handlers y usa el primero que maneje el
    mensaje (retorna != 0). El orden define la prioridad. Un handler que retorna 0
    significa "no era para mí". Si ninguno lo maneja, retorna 0 (mensaje descartado)."""

    def __init__(self, handlers):
        self._handlers = list(handlers)

    async def handle(self, text, chat_title=None) -> int:
        for handler in self._handlers:
            try:
                n = await handler.handle(text, chat_title)
            except Exception:
                logger.exception(
                    "Handler %s falló procesando un mensaje; se prueba el siguiente",
                    type(handler).__name__,
                )
                continue
            if n:
                return n
        return 0
