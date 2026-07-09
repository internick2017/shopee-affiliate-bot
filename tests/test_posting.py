import asyncio

from src.posting import post_offer


class FakePoster:
    def __init__(self):
        self.texts = []
        self.files = []

    async def post_text(self, text):
        self.texts.append(text)

    async def post(self, image, text):
        self.files.append((image, text))


def test_posts_text_when_no_photo():
    poster = FakePoster()
    asyncio.run(post_offer(poster, "un post"))
    assert poster.texts == ["un post"]
    assert poster.files == []


def test_posts_photo_with_caption_when_photo_present():
    poster = FakePoster()
    sentinel = object()  # el objeto `photo` de Telethon, reenviado por referencia
    asyncio.run(post_offer(poster, "un post", sentinel))
    assert poster.files == [(sentinel, "un post")]
    assert poster.texts == []
