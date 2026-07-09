import asyncio

from src.mercadolivre_review import (
    DEFAULT_MARKER,
    MercadoLivreReviewPipeline,
    build_mercadolivre_review_message,
    has_mercadolivre_links,
    mercadolivre_dedup_key,
)

# Mensaje real de Promocasinha (el link resuelve a /social/promocasinha?ref=<cifrado>).
PROMOCASINHA_ML = (
    "Smart TV Hisense de 65 polegadas Vidaa 65u6qv Uled 4k\n"
    " \n"
    "Por: R$ 3.070,99 à vista\n"
    "\n"
    "Use o cupom TVCASASBAHIA\n"
    "\n"
    "Mercado Livre:\n"
    "Compre em: https://meli.la/1Q8EMBW\n"
    "\n"
    "Promoção por tempo limitado."
)


class FakePoster:
    def __init__(self):
        self.posts = []

    async def post_text(self, text):
        self.posts.append(text)


class FakeDedup:
    def __init__(self):
        self.keys = {}

    def seen(self, key):
        return key in self.keys

    def mark(self, key):
        self.keys[key] = True


def test_has_mercadolivre_links():
    assert has_mercadolivre_links("veja https://meli.la/1Q8EMBW agora")
    assert has_mercadolivre_links("https://www.mercadolivre.com.br/social/x?ref=abc")
    assert has_mercadolivre_links("https://mercadolivre.com/sec/2abcDEF")


def test_has_mercadolivre_links_false():
    assert not has_mercadolivre_links("https://www.amazon.com.br/dp/X")
    assert not has_mercadolivre_links("https://s.shopee.com.br/abc")
    assert not has_mercadolivre_links("")
    assert not has_mercadolivre_links(None)


def test_build_message_none_without_ml():
    assert build_mercadolivre_review_message("sem mercado livre aqui") is None


def test_build_message_marks_and_keeps_name_price_and_coupon():
    msg = build_mercadolivre_review_message(PROMOCASINHA_ML)
    assert msg.startswith(DEFAULT_MARKER)
    # lo que el owner necesita para armar el link a mano
    assert "Smart TV Hisense de 65 polegadas Vidaa 65u6qv Uled 4k" in msg
    assert "R$ 3.070,99" in msg
    assert "TVCASASBAHIA" in msg
    assert "https://meli.la/1Q8EMBW" in msg


def test_build_message_strips_competitor_footer():
    text = (
        "Produto X\n"
        "https://meli.la/abc\n"
        "🛍 Grupos de promos:\n"
        "https://ctlinks.com.br"
    )
    msg = build_mercadolivre_review_message(text)
    assert "ctlinks.com.br" not in msg
    assert "Grupos de promos" not in msg


def test_dedup_key_ignores_query_params():
    a = mercadolivre_dedup_key("https://meli.la/1Q8EMBW")
    b = mercadolivre_dedup_key("outro\nhttps://meli.la/1Q8EMBW?utm=x")
    assert a is not None and a == b


def test_dedup_key_differs_per_product():
    assert mercadolivre_dedup_key("https://meli.la/AAA") != mercadolivre_dedup_key(
        "https://meli.la/BBB"
    )


def test_dedup_key_does_not_collide_with_shopee():
    from src.shopee_review import shopee_dedup_key

    ml = mercadolivre_dedup_key("https://meli.la/AAA")
    shopee = shopee_dedup_key("https://s.shopee.com.br/AAA")
    assert ml != shopee


def test_pipeline_forwards_ml_offer():
    poster = FakePoster()
    pipe = MercadoLivreReviewPipeline(poster)
    assert asyncio.run(pipe.handle(PROMOCASINHA_ML)) == 1
    assert len(poster.posts) == 1
    assert poster.posts[0].startswith(DEFAULT_MARKER)


def test_pipeline_skips_when_no_ml():
    poster = FakePoster()
    pipe = MercadoLivreReviewPipeline(poster)
    assert asyncio.run(pipe.handle("https://www.amazon.com.br/dp/X")) == 0
    assert poster.posts == []


def test_pipeline_skips_duplicate():
    poster = FakePoster()
    pipe = MercadoLivreReviewPipeline(poster, dedup=FakeDedup())
    assert asyncio.run(pipe.handle(PROMOCASINHA_ML)) == 1
    assert asyncio.run(pipe.handle(PROMOCASINHA_ML)) == 1
    assert len(poster.posts) == 1


class FakePhotoPoster(FakePoster):
    def __init__(self):
        super().__init__()
        self.files = []

    async def post(self, image, text):
        self.files.append((image, text))


def test_forward_carries_source_photo():
    poster = FakePhotoPoster()
    pipe = MercadoLivreReviewPipeline(poster)
    photo = object()

    assert asyncio.run(pipe.handle(PROMOCASINHA_ML, photo=photo)) == 1

    assert poster.posts == []
    assert len(poster.files) == 1
    imagen, texto = poster.files[0]
    assert imagen is photo
    assert texto.startswith(DEFAULT_MARKER)
