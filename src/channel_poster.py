class ChannelPoster:
    """Publica imagen + texto en el canal privado de Telegram.

    Usa la misma sesión de Telethon que el listener (la cuenta de Nick postea
    a su propio canal).
    """

    # Telegram corta los captions de foto a 1024 caracteres. Un post más largo se
    # manda como foto + mensaje aparte, en vez de perder el final del texto.
    CAPTION_LIMIT = 1024

    def __init__(self, client, channel):
        self._client = client
        self._channel = channel

    async def post(self, image, text: str) -> None:
        """`image` puede ser una URL o un objeto de media de Telethon (p. ej. el
        `photo` del mensaje original, que se reenvía por referencia sin descargarlo)."""
        if len(text) > self.CAPTION_LIMIT:
            await self._client.send_file(self._channel, file=image)
            await self.post_text(text)
            return
        await self._client.send_file(self._channel, file=image, caption=text)

    async def post_text(self, text: str) -> None:
        await self._client.send_message(self._channel, text, link_preview=True)
