from src.amazon_pipeline import AmazonPipeline
from src.post_builder import HookBank
from tests.fakes import FakeDedup

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
    "🔥 Outro produto\n\n💵 R$ 25\nhttps://www.amazon.com.br/dp/B0F8BQ3KYW?tag=crowmantech-20\n"
)


async def test_same_asin_from_another_group_is_not_reposted():
    poster = _FakePoster()
    dedup = FakeDedup()
    pipeline = AmazonPipeline(TAG, poster, HookBank([HOOK]), dedup=dedup)

    assert await pipeline.handle(AMAZON_TEXT, "Crowman") == 1
    assert len(poster.posts) == 1

    # mismo ASIN (B07QZB3PDY), otro grupo, otro texto y otro tag de origen
    assert await pipeline.handle(AMAZON_TEXT_OTRO_GRUPO, "IAchados") == 1
    assert len(poster.posts) == 1  # no se volvió a postear


async def test_different_asin_is_posted():
    poster = _FakePoster()
    dedup = FakeDedup()
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
    dedup = FakeDedup()
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
    dedup = FakeDedup()
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


# --- shortlinks (Promocasinha) ---

PROMOCASINHA_TEXT = (
    "Espuma Mágica Aerossol 400ml / 370g\n"
    " \n"
    "Por: R$ 16,90\n"
    "\n"
    "Amazon:\n"
    "Compre em: https://link.amazon/B0iFvhSgZ\n"
    "\n"
    "Promoção por tempo limitado."
)


def _fake_expand(resuelto):
    def expand(text, **kwargs):
        return text.replace("https://link.amazon/B0iFvhSgZ", resuelto)

    return expand


async def test_resolves_shortlink_and_posts():
    poster = _FakePoster()
    pipeline = AmazonPipeline(
        TAG,
        poster,
        HookBank([HOOK]),
        expand=_fake_expand("https://www.amazon.com.br/dp/B076X7T368"),
    )

    assert await pipeline.handle(PROMOCASINHA_TEXT, "Promocasinha") == 1
    assert len(poster.posts) == 1
    assert "Espuma Mágica Aerossol 400ml / 370g" in poster.posts[0]
    assert "R$ 16,90" in poster.posts[0]
    assert f"dp/B076X7T368?tag={TAG}" in poster.posts[0]
    assert "link.amazon" not in poster.posts[0]


async def test_unresolvable_shortlink_is_dropped():
    """Si el shortlink no resuelve, el texto queda igual y no hay link de Amazon."""
    poster = _FakePoster()
    pipeline = AmazonPipeline(TAG, poster, HookBank([HOOK]), expand=lambda text, **kw: text)

    assert await pipeline.handle(PROMOCASINHA_TEXT, "Promocasinha") == 0
    assert poster.posts == []


async def test_shortlink_dedups_by_resolved_asin():
    """El mismo producto vía shortlink (Promocasinha) y vía link directo (Crowman)."""
    poster = _FakePoster()
    dedup = FakeDedup()
    pipeline = AmazonPipeline(
        TAG,
        poster,
        HookBank([HOOK]),
        dedup=dedup,
        expand=_fake_expand("https://www.amazon.com.br/dp/B076X7T368"),
    )

    directo = (
        "Espuma Mágica Aerossol 400ml / 370g\n"
        "🔥 R$ 11,83 à vista\n"
        "🛍 https://www.amazon.com.br/dp/B076X7T368?tag=crowmantech-20"
    )

    assert await pipeline.handle(directo, "Crowman") == 1
    assert await pipeline.handle(PROMOCASINHA_TEXT, "Promocasinha") == 1
    assert len(poster.posts) == 1  # el segundo es el mismo ASIN


async def test_no_network_when_no_shortlink():
    """Un mensaje sin shortlink no debe tocar la red."""

    def _boom(text, **kw):
        raise AssertionError("no debería resolverse nada")

    poster = _FakePoster()
    pipeline = AmazonPipeline(TAG, poster, HookBank([HOOK]), expand=_boom)
    assert await pipeline.handle(AMAZON_TEXT, "Crowman") == 1
    assert len(poster.posts) == 1


# --- foto del mensaje original ---


class _FakePhotoPoster(_FakePoster):
    def __init__(self):
        super().__init__()
        self.files = []

    async def post(self, image, text):
        self.files.append((image, text))


async def test_post_carries_source_photo():
    poster = _FakePhotoPoster()
    pipeline = _pipeline(poster)
    photo = object()

    assert await pipeline.handle(AMAZON_TEXT, "Crowman", photo=photo) == 1

    assert poster.posts == []
    assert len(poster.files) == 1
    imagen, texto = poster.files[0]
    assert imagen is photo
    assert "Smirnoff Vodka 600Ml" in texto


async def test_post_without_photo_still_text_only():
    poster = _FakePhotoPoster()
    pipeline = _pipeline(poster)
    assert await pipeline.handle(AMAZON_TEXT, "Crowman") == 1
    assert poster.files == []
    assert len(poster.posts) == 1


async def test_key_is_released_when_posting_fails():
    """Un post fallido no debe dar la oferta por publicada: se reintenta después."""

    class _BrokenPoster:
        def __init__(self):
            self.posts = []
            self.fail = True

        async def post_text(self, text):
            if self.fail:
                raise RuntimeError("Telegram caído")
            self.posts.append(text)

        async def post(self, image, text):
            await self.post_text(text)

    poster = _BrokenPoster()
    dedup = FakeDedup()
    pipeline = AmazonPipeline(TAG, poster, HookBank([HOOK, HOOK]), dedup=dedup)

    try:
        await pipeline.handle(AMAZON_TEXT)
    except RuntimeError:
        pass
    else:
        raise AssertionError("el fallo del poster debía propagar")
    assert dedup.keys == {}

    poster.fail = False
    assert await pipeline.handle(AMAZON_TEXT) == 1
    assert len(poster.posts) == 1
