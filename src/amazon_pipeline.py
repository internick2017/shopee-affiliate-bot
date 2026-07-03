import logging

from .lanny_post import build_lanny_amazon_post

logger = logging.getLogger(__name__)


class AmazonPipeline:
    """Turns a promo message into a Lanny-style Amazon post and publishes it."""

    def __init__(self, tag, poster, hookbank):
        self._tag = tag
        self._poster = poster
        self._hookbank = hookbank

    async def handle(self, text, chat_title=None) -> int:
        post = build_lanny_amazon_post(text, self._tag, self._hookbank.next())
        if not post:
            return 0
        await self._poster.post_text(post)
        logger.info("Post de Amazon (estilo Lanny) publicado al canal")
        return 1
