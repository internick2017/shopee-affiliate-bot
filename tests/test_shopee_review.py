import asyncio

from src.shopee_review import (
    DEFAULT_MARKER,
    has_shopee_links,
    build_shopee_review_message,
    ShopeeReviewPipeline,
)


class FakePoster:
    def __init__(self):
        self.posts = []

    async def post_text(self, text):
        self.posts.append(text)


def test_has_shopee_links_detects_domains():
    assert has_shopee_links("veja https://s.shopee.com.br/30mAvLd6Uk agora")
    assert has_shopee_links("https://shopee.com.br/product/1/2")
    assert has_shopee_links("https://shp.ee/abc123")


def test_has_shopee_links_false():
    assert not has_shopee_links("https://www.amazon.com.br/dp/X")
    assert not has_shopee_links("")
    assert not has_shopee_links(None)


def test_build_shopee_review_message_none_without_shopee():
    assert build_shopee_review_message("sem shopee aqui") is None


def test_build_shopee_review_message_marks_and_keeps_links():
    text = (
        "📺 Smart TV 39\n"
        "🔥 POR 841,07 no Pix\n"
        "🔗 https://s.shopee.com.br/8V77TB32CU\n"
        "🔗 https://s.shopee.com.br/1VxN8JY0v7?lp=aff"
    )
    msg = build_shopee_review_message(text)
    assert msg.startswith(DEFAULT_MARKER)
    assert "https://s.shopee.com.br/8V77TB32CU" in msg
    assert "https://s.shopee.com.br/1VxN8JY0v7?lp=aff" in msg
    assert "Smart TV 39" in msg


def test_build_shopee_review_message_strips_competitor_footer():
    text = (
        "Produto X\n"
        "https://s.shopee.com.br/abc\n"
        "🛍 Grupos de promos:\n"
        "https://ctlinks.com.br"
    )
    msg = build_shopee_review_message(text)
    assert "ctlinks.com.br" not in msg
    assert "Grupos de promos" not in msg


def test_pipeline_posts_when_shopee():
    poster = FakePoster()
    pipe = ShopeeReviewPipeline(poster)
    n = asyncio.run(pipe.handle("🔗 https://s.shopee.com.br/abc"))
    assert n == 1
    assert len(poster.posts) == 1
    assert poster.posts[0].startswith(DEFAULT_MARKER)


def test_pipeline_skips_when_no_shopee():
    poster = FakePoster()
    pipe = ShopeeReviewPipeline(poster)
    n = asyncio.run(pipe.handle("https://www.amazon.com.br/dp/X"))
    assert n == 0
    assert poster.posts == []
