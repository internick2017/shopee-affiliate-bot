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

    async def handle(self, text, chat_title=None):
        self.calls += 1
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

        async def handle(self, text, chat_title=None):
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
        async def handle(self, text, chat_title=None):
            raise RuntimeError("boom")

    pipe = OfferPipeline([RaisingHandler(), RaisingHandler()])
    assert asyncio.run(pipe.handle("x")) == 0
