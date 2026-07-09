import asyncio

from src.offer_pipeline import OfferPipeline
from src.amazon_pipeline import AmazonPipeline
from src.shopee_review import ShopeeReviewPipeline, DEFAULT_MARKER
from src.post_builder import HookBank


class FakeHandler:
    def __init__(self, ret, name):
        self.ret = ret
        self.name = name
        self.calls = 0
        self.photos = []

    async def handle(self, text, chat_title=None, photo=None):
        self.calls += 1
        self.photos.append(photo)
        return self.ret


class FakePoster:
    def __init__(self):
        self.posts = []

    async def post_text(self, text):
        self.posts.append(text)


def test_uses_first_handler_that_returns_nonzero():
    a = FakeHandler(1, "a")
    b = FakeHandler(1, "b")
    pipe = OfferPipeline([a, b])
    n = asyncio.run(pipe.handle("x"))
    assert n == 1
    assert a.calls == 1
    assert b.calls == 0  # no se llama al segundo si el primero manejó


def test_falls_through_to_next_handler():
    a = FakeHandler(0, "a")
    b = FakeHandler(1, "b")
    pipe = OfferPipeline([a, b])
    n = asyncio.run(pipe.handle("x"))
    assert n == 1
    assert a.calls == 1
    assert b.calls == 1


def test_returns_zero_when_nobody_handles():
    a = FakeHandler(0, "a")
    b = FakeHandler(0, "b")
    pipe = OfferPipeline([a, b])
    assert asyncio.run(pipe.handle("x")) == 0


def test_integration_shopee_message_forwarded():
    poster = FakePoster()
    amazon = AmazonPipeline("ofertaslanny-20", poster, HookBank(["GANCHO"]))
    shopee = ShopeeReviewPipeline(poster)
    pipe = OfferPipeline([amazon, shopee])
    text = "📺 Smart TV\n🔥 POR 841,07 no Pix\n🔗 https://s.shopee.com.br/8V77TB32CU"
    n = asyncio.run(pipe.handle(text))
    assert n == 1
    assert len(poster.posts) == 1
    assert poster.posts[0].startswith(DEFAULT_MARKER)


def test_integration_mercadolivre_message_dropped():
    poster = FakePoster()
    amazon = AmazonPipeline("ofertaslanny-20", poster, HookBank(["GANCHO"]))
    shopee = ShopeeReviewPipeline(poster)
    pipe = OfferPipeline([amazon, shopee])
    text = "👟 Tênis\n🔥 DE 399,99 | POR 218,11 em 6x\n🔗 https://meli.la/2E9VURp"
    n = asyncio.run(pipe.handle(text))
    assert n == 0
    assert poster.posts == []


def test_integration_amazon_message_builds_lanny_not_shopee():
    poster = FakePoster()
    amazon = AmazonPipeline("ofertaslanny-20", poster, HookBank(["GANCHO"]))
    shopee = ShopeeReviewPipeline(poster)
    pipe = OfferPipeline([amazon, shopee])
    text = (
        "🍔 Heinz Maionese Alho Tostado Com Ervas 215g\n"
        "🔥 DE 13,59 | POR 9,16\n"
        "🔗 https://www.amazon.com.br/dp/B0B25NN5HL?tag=iachadospromo-20"
    )
    n = asyncio.run(pipe.handle(text))
    assert n == 1
    assert len(poster.posts) == 1
    assert "Heinz Maionese Alho Tostado Com Ervas 215g" in poster.posts[0]
    assert not poster.posts[0].startswith(DEFAULT_MARKER)


def test_raising_handler_is_isolated_and_next_handler_runs():
    class RaisingHandler:
        def __init__(self):
            self.calls = 0

        async def handle(self, text, chat_title=None, photo=None):
            self.calls += 1
            raise RuntimeError("boom")

    raising = RaisingHandler()
    good = FakeHandler(1, "good")
    pipe = OfferPipeline([raising, good])
    n = asyncio.run(pipe.handle("x"))
    assert n == 1
    assert raising.calls == 1
    assert good.calls == 1


def test_all_handlers_raise_returns_zero():
    class RaisingHandler:
        async def handle(self, text, chat_title=None, photo=None):
            raise RuntimeError("boom")

    pipe = OfferPipeline([RaisingHandler(), RaisingHandler()])
    assert asyncio.run(pipe.handle("x")) == 0


# --- router completo: Amazon + Shopee + Mercado Livre ---

def _full_pipeline(amazon_poster, shopee_poster, ml_poster):
    from src.mercadolivre_review import MercadoLivreReviewPipeline

    return OfferPipeline([
        AmazonPipeline("ofertaslanny-20", amazon_poster, HookBank(["GANCHO"])),
        ShopeeReviewPipeline(shopee_poster),
        MercadoLivreReviewPipeline(ml_poster),
    ])


def test_ml_message_goes_to_ml_poster_only():
    from src.mercadolivre_review import DEFAULT_MARKER as ML_MARKER

    amazon_poster, shopee_poster, ml_poster = FakePoster(), FakePoster(), FakePoster()
    pipe = _full_pipeline(amazon_poster, shopee_poster, ml_poster)

    text = "👟 Tênis\n🔥 DE 399,99 | POR 218,11 em 6x\n🔗 https://meli.la/2E9VURp"
    assert asyncio.run(pipe.handle(text)) == 1
    assert amazon_poster.posts == []
    assert shopee_poster.posts == []
    assert len(ml_poster.posts) == 1
    assert ml_poster.posts[0].startswith(ML_MARKER)


def test_each_platform_goes_to_its_own_channel():
    amazon_poster, shopee_poster, ml_poster = FakePoster(), FakePoster(), FakePoster()
    pipe = _full_pipeline(amazon_poster, shopee_poster, ml_poster)

    amazon = (
        "🍔 Heinz Maionese Alho Tostado Com Ervas 215g\n"
        "🔥 DE 13,59 | POR 9,16\n"
        "🔗 https://www.amazon.com.br/dp/B0B25NN5HL?tag=iachadospromo-20"
    )
    shopee = "📺 Smart TV\n🔥 POR 841,07 no Pix\n🔗 https://s.shopee.com.br/8V77TB32CU"
    ml = "👟 Tênis\n🔥 POR 218,11\n🔗 https://meli.la/2E9VURp"

    for text in (amazon, shopee, ml):
        assert asyncio.run(pipe.handle(text)) == 1

    assert len(amazon_poster.posts) == 1
    assert len(shopee_poster.posts) == 1
    assert len(ml_poster.posts) == 1


def test_amazon_message_with_ml_link_is_forwarded_to_ml():
    """Amazon se rinde ante un mensaje con links de ML; lo recoge el handler de ML."""
    from src.mercadolivre_review import DEFAULT_MARKER as ML_MARKER

    amazon_poster, shopee_poster, ml_poster = FakePoster(), FakePoster(), FakePoster()
    pipe = _full_pipeline(amazon_poster, shopee_poster, ml_poster)

    mixto = (
        "Produto X\n🔥 R$ 19\n"
        "https://www.amazon.com.br/dp/B07QZB3PDY?tag=x-20\n"
        "https://meli.la/2E9VURp"
    )
    assert asyncio.run(pipe.handle(mixto)) == 1
    assert amazon_poster.posts == []
    assert len(ml_poster.posts) == 1
    assert ml_poster.posts[0].startswith(ML_MARKER)
