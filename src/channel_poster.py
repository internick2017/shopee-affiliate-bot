class ChannelPoster:
    """Publica imagen + texto en el canal privado de Telegram.

    Usa la misma sesión de Telethon que el listener (la cuenta de Nick postea
    a su propio canal).
    """

    def __init__(self, client, channel):
        self._client = client
        self._channel = channel

    async def post(self, image_url: str, text: str) -> None:
        await self._client.send_file(
            self._channel, file=image_url, caption=text
        )
