"""Cómo publica un handler: con la foto del mensaje original si la hay."""


async def post_offer(poster, text, photo=None) -> None:
    """Publica `text` en el canal, adjuntando `photo` si el mensaje original traía una.

    Los tres canales fuente postean siempre con foto, así que en la práctica el post
    sale ilustrado. La foto se reenvía por referencia de Telegram (no se descarga).
    Sin foto, cae al mensaje de texto de siempre.
    """
    if photo is None:
        await poster.post_text(text)
        return
    await poster.post(photo, text)
