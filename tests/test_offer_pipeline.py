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


def test_every_handler_sees_the_message_and_counts_are_summed():
    """Un mensaje puede traer productos de varias plataformas: nadie se lo queda entero."""
    a = FakeHandler(1, "a")
    b = FakeHandler(1, "b")
    pipe = OfferPipeline([a, b])
    n = asyncio.run(pipe.handle("x"))
    assert n == 2
    assert a.calls == 1
    assert b.calls == 1


def test_handler_can_publish_several_offers_from_one_message():
    a = FakeHandler(3, "a")
    b = FakeHandler(0, "b")
    pipe = OfferPipeline([a, b])
    assert asyncio.run(pipe.handle("x")) == 3


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


def test_mixed_message_posts_amazon_and_forwards_ml():
    """Crowman mezcla bloques de Amazon y de ML en un mensaje: cada handler toma el suyo."""
    from src.mercadolivre_review import DEFAULT_MARKER as ML_MARKER

    amazon_poster, shopee_poster, ml_poster = FakePoster(), FakePoster(), FakePoster()
    pipe = _full_pipeline(amazon_poster, shopee_poster, ml_poster)

    mixto = (
        "Kit 12 Cuecas Boxer Reebok\n"
        "🔥 R$ 94 à vista\n"
        "🛒https://www.amazon.com.br/dp/B0CW25HCNG?tag=crowmantech-20\n"
        "\n"
        "Braé Essential Kit Fluido 260ml\n"
        "🔥 R$ 119,77 À vista\n"
        "🛒https://meli.la/19ZAxqR"
    )
    assert asyncio.run(pipe.handle(mixto)) == 2

    # el producto de Amazon se monetiza solo...
    assert len(amazon_poster.posts) == 1
    assert "Kit 12 Cuecas Boxer Reebok" in amazon_poster.posts[0]
    assert "dp/B0CW25HCNG?tag=ofertaslanny-20" in amazon_poster.posts[0]
    # ...y el de ML va a revisión manual, sin robarse el mensaje entero
    assert len(ml_poster.posts) == 1
    assert ml_poster.posts[0].startswith(ML_MARKER)


def test_ml_block_price_is_not_attached_to_the_amazon_product():
    """El precio del bloque de ML no debe colarse en el post de Amazon."""
    amazon_poster, shopee_poster, ml_poster = FakePoster(), FakePoster(), FakePoster()
    pipe = _full_pipeline(amazon_poster, shopee_poster, ml_poster)

    mixto = (
        "Braé Essential Kit Fluido 260ml\n"
        "🔥 R$ 119,77 À vista\n"
        "🛒https://meli.la/19ZAxqR\n"
        "\n"
        "Kit 4 Bermuda Shorts Tactel\n"
        "🔥 R$ 55 em até 2x s/ juros\n"
        "🛒https://www.amazon.com.br/dp/B0FFNRMR4L?tag=crowmantech-20"
    )
    asyncio.run(pipe.handle(mixto))

    assert len(amazon_poster.posts) == 1
    post = amazon_poster.posts[0]
    assert "Kit 4 Bermuda Shorts Tactel" in post
    assert "R$ 55,00" in post
    assert "119,77" not in post
    assert "Braé" not in post
