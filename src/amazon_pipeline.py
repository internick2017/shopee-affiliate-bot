import logging

from .amazon_retagger import build_amazon_post

logger = logging.getLogger(__name__)


class AmazonPipeline:
    """Turns a promo message into a retagged Amazon post and publishes it."""

    def __init__(self, tag, poster):
        self._tag = tag
        self._poster = poster

    async def handle(self, text, chat_title=None) -> int:
        post = build_amazon_post(text, self._tag)
        if not post:
            return 0
        await self._poster.post_text(post)
        logger.info("Post de Amazon publicado al canal")
        return 1
