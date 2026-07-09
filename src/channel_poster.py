import asyncio
import logging

logger = logging.getLogger(__name__)


def flood_wait_seconds(exc: BaseException):
    """Segundos que Telegram pide esperar, o None si el error no es un FloodWait.

    Se detecta por nombre y no con `isinstance`: telethon se importa de forma perezosa
    en todo el proyecto (el listener hace lo mismo), y esto permite testear sin él.
    """
    if type(exc).__name__ != "FloodWaitError":
        return None
    seconds = getattr(exc, "seconds", None)
    return seconds if isinstance(seconds, int) else None


class ChannelPoster:
    """Publica imagen + texto en el canal privado de Telegram.

    Usa la misma sesión de Telethon que el listener (la cuenta de Nick postea
    a su propio canal).
    """

    # Telegram corta los captions de foto a 1024 caracteres. Un post más largo se
    # manda como foto + mensaje aparte, en vez de perder el final del texto.
    CAPTION_LIMIT = 1024

    # Telegram limita las ráfagas con FloodWait. Se espera y se reintenta, en vez de
    # perder la oferta. Si pide más que el tope, no vale la pena bloquear el bot:
    # la excepción sube y OfferPipeline la loguea.
    MAX_RETRIES = 2
    MAX_WAIT_SECONDS = 300

    def __init__(self, client, channel, *, sleep=asyncio.sleep):
        self._client = client
        self._channel = channel
        self._sleep = sleep

    async def _retrying(self, send):
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                return await send()
            except Exception as exc:
                wait = flood_wait_seconds(exc)
                if wait is None or attempt == self.MAX_RETRIES:
                    raise
                if wait > self.MAX_WAIT_SECONDS:
                    logger.error(
                        "Telegram pide esperar %ss, más que el tope de %ss; se abandona",
                        wait,
                        self.MAX_WAIT_SECONDS,
                    )
                    raise
                logger.warning(
                    "FloodWait de Telegram: se espera %ss y se reintenta (%d/%d)",
                    wait,
                    attempt,
                    self.MAX_RETRIES - 1,
                )
                # +1s de colchón: Telegram rechaza si se vuelve justo al filo.
                await self._sleep(wait + 1)

    async def post(self, image, text: str) -> None:
        """`image` puede ser una URL o un objeto de media de Telethon (p. ej. el
        `photo` del mensaje original, que se reenvía por referencia sin descargarlo)."""
        if len(text) > self.CAPTION_LIMIT:
            await self._retrying(
                lambda: self._client.send_file(self._channel, file=image)
            )
            await self.post_text(text)
            return
        await self._retrying(
            lambda: self._client.send_file(self._channel, file=image, caption=text)
        )

    async def post_text(self, text: str) -> None:
        await self._retrying(
            lambda: self._client.send_message(self._channel, text, link_preview=True)
        )
