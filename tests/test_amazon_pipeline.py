from src.amazon_pipeline import AmazonPipeline

TAG = "ofertaslanny-20"

AMAZON_TEXT = (
    "🔥 Smirnoff Vodka 600Ml\n\n"
    "💵 R$ 19\n"
    "https://www.amazon.com.br/dp/B07QZB3PDY?tag=crowmantech-20\n\n"
    "anúncio\n\n"
    "🛍 Grupos de promos:\n"
    "https://ctlinks.com.br"
)

MERCADOLIVRE_TEXT = "🔥 Oferta boa\n\n💵 R$ 19\nhttps://meli.la/1ShxGBP\n\nanúncio"

PLAIN_TEXT = "Bom dia grupo, alguém sabe se ainda tem estoque?"


class _FakePoster:
    def __init__(self):
        self.posts = []

    async def post_text(self, text):
        self.posts.append(text)


async def test_posts_amazon_offer():
    poster = _FakePoster()
    pipeline = AmazonPipeline(TAG, poster)

    result = await pipeline.handle(AMAZON_TEXT, "Crowman Promos")

    assert result == 1
    assert len(poster.posts) == 1
    assert TAG in poster.posts[0]
    assert "crowmantech-20" not in poster.posts[0]


async def test_skips_mercadolivre():
    poster = _FakePoster()
    pipeline = AmazonPipeline(TAG, poster)

    result = await pipeline.handle(MERCADOLIVRE_TEXT, "Crowman Promos")

    assert result == 0
    assert poster.posts == []


async def test_skips_when_no_links():
    poster = _FakePoster()
    pipeline = AmazonPipeline(TAG, poster)

    result = await pipeline.handle(PLAIN_TEXT, "Crowman Promos")

    assert result == 0
    assert poster.posts == []
