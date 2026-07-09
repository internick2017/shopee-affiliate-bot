from src.amazon_pipeline import AmazonPipeline
from src.post_builder import HookBank

TAG = "ofertaslanny-20"
HOOK = "GANCHO DE PRUEBA 🔥"

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


def _pipeline(poster):
    return AmazonPipeline(TAG, poster, HookBank([HOOK]))


async def test_posts_amazon_offer():
    poster = _FakePoster()
    pipeline = _pipeline(poster)

    result = await pipeline.handle(AMAZON_TEXT, "Crowman Promos")

    assert result == 1
    assert len(poster.posts) == 1
    assert TAG in poster.posts[0]
    assert "crowmantech-20" not in poster.posts[0]
    assert "🛍️ " in poster.posts[0]
    assert poster.posts[0].startswith(HOOK)


async def test_skips_mercadolivre():
    poster = _FakePoster()
    pipeline = _pipeline(poster)

    result = await pipeline.handle(MERCADOLIVRE_TEXT, "Crowman Promos")

    assert result == 0
    assert poster.posts == []


async def test_skips_when_no_links():
    poster = _FakePoster()
    pipeline = _pipeline(poster)

    result = await pipeline.handle(PLAIN_TEXT, "Crowman Promos")

    assert result == 0
    assert poster.posts == []


# --- dedup ---

AMAZON_TEXT_OTRO_GRUPO = (
    "🔥 Smirnoff Vodka 600Ml — MESMO PRODUTO, OUTRO GRUPO\n\n"
    "💵 R$ 19\n"
    "https://www.amazon.com.br/dp/B07QZB3PDY?th=1&psc=1&tag=iachadospromo-20\n\n"
    "🛍️ IAchados"
)

AMAZON_TEXT_OTRO_PRODUCTO = (
    "🔥 Outro produto\n\n"
    "💵 R$ 25\n"
    "https://www.amazon.com.br/dp/B0F8BQ3KYW?tag=crowmantech-20\n"
)


class _FakeDedup:
    def __init__(self):
        self.keys = {}

    def seen(self, key):
        return key in self.keys

    def mark(self, key):
        self.keys[key] = True


async def test_same_asin_from_another_group_is_not_reposted():
    poster = _FakePoster()
    dedup = _FakeDedup()
    pipeline = AmazonPipeline(TAG, poster, HookBank([HOOK]), dedup=dedup)

    assert await pipeline.handle(AMAZON_TEXT, "Crowman") == 1
    assert len(poster.posts) == 1

    # mismo ASIN (B07QZB3PDY), otro grupo, otro texto y otro tag de origen
    assert await pipeline.handle(AMAZON_TEXT_OTRO_GRUPO, "IAchados") == 1
    assert len(poster.posts) == 1  # no se volvió a postear


async def test_different_asin_is_posted():
    poster = _FakePoster()
    dedup = _FakeDedup()
    pipeline = AmazonPipeline(TAG, poster, HookBank([HOOK]), dedup=dedup)

    assert await pipeline.handle(AMAZON_TEXT, "Crowman") == 1
    assert await pipeline.handle(AMAZON_TEXT_OTRO_PRODUCTO, "Crowman") == 1
    assert len(poster.posts) == 2


class _CountingHookBank:
    """HookBank que cuenta cuántas veces le pidieron un gancho. No se puede usar
    el HookBank real: elige al azar, así que el gancho de cada post no es predecible."""

    def __init__(self):
        self.calls = 0

    def next(self):
        self.calls += 1
        return "GANCHO"


async def test_duplicate_does_not_consume_a_hook():
    """Un duplicado no debe gastar un gancho: se descarta antes de armar el post."""
    poster = _FakePoster()
    dedup = _FakeDedup()
    hookbank = _CountingHookBank()
    pipeline = AmazonPipeline(TAG, poster, hookbank, dedup=dedup)

    await pipeline.handle(AMAZON_TEXT, "Crowman")
    assert hookbank.calls == 1

    await pipeline.handle(AMAZON_TEXT_OTRO_GRUPO, "IAchados")  # duplicado
    assert hookbank.calls == 1  # no pidió gancho nuevo

    await pipeline.handle(AMAZON_TEXT_OTRO_PRODUCTO, "Crowman")
    assert hookbank.calls == 2


async def test_message_that_builds_no_post_is_not_marked():
    """Si no se pudo armar el post (sin precio), no se marca como visto."""
    poster = _FakePoster()
    dedup = _FakeDedup()
    pipeline = AmazonPipeline(TAG, poster, HookBank([HOOK]), dedup=dedup)

    sin_precio = "Produto legal\nhttps://www.amazon.com.br/dp/B07QZB3PDY?tag=x-20"
    assert await pipeline.handle(sin_precio, "Crowman") == 0
    assert dedup.keys == {}


async def test_works_without_dedup():
    """dedup es opcional: sin store, postea siempre (comportamiento anterior)."""
    poster = _FakePoster()
    pipeline = _pipeline(poster)
    await pipeline.handle(AMAZON_TEXT, "Crowman")
    await pipeline.handle(AMAZON_TEXT_OTRO_GRUPO, "IAchados")
    assert len(poster.posts) == 2
