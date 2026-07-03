from decimal import Decimal

from src.dedup_store import DedupStore
from src.link_extractor import extract_shopee_links
from src.models import Product
from src.pipeline import Pipeline
from src.post_builder import HookBank
from src.shopee_client import MockShopeeClient


class _FakePoster:
    def __init__(self):
        self.posts = []

    async def post(self, image_url, text):
        self.posts.append({"image_url": image_url, "text": text})


def _resolver_for(shop_id, item_id):
    def _resolve(url):
        return (shop_id, item_id)
    return _resolve


def _pipeline(tmp_path, poster, product):
    return Pipeline(
        extractor=extract_shopee_links,
        resolver=_resolver_for(222, 111),
        dedup=DedupStore(tmp_path / "d.db"),
        client=MockShopeeClient(product=product),
        hookbank=HookBank(["GANCHO DE PRUEBA 🔥"]),
        poster=poster,
    )


def _sample_product():
    return Product(
        item_id=111,
        shop_id=222,
        name="Saco De Lavar Tênis",
        price_final=Decimal("16.98"),
        image_url="https://example.com/img.jpg",
        affiliate_link="https://s.shopee.com.br/LANNY",
    )


async def test_handle_builds_and_posts_one_offer(tmp_path):
    poster = _FakePoster()
    pipeline = _pipeline(tmp_path, poster, _sample_product())
    text = "CORRE! 🛒 Compre aqui: https://s.shopee.com.br/6KxbHWtz5C"

    count = await pipeline.handle(text, chat_title="Ofertas BR")

    assert count == 1
    assert len(poster.posts) == 1
    post = poster.posts[0]
    assert post["image_url"] == "https://example.com/img.jpg"
    assert "🛍️ Saco De Lavar Tênis" in post["text"]
    assert "✅ Por: R$ 16,98 😱🛒" in post["text"]
    assert "https://s.shopee.com.br/LANNY" in post["text"]
    assert post["text"].startswith("GANCHO DE PRUEBA 🔥")


async def test_handle_dedups_same_product(tmp_path):
    poster = _FakePoster()
    pipeline = _pipeline(tmp_path, poster, _sample_product())
    text = "🛒 Compre aqui: https://s.shopee.com.br/6KxbHWtz5C"

    first = await pipeline.handle(text)
    second = await pipeline.handle(text)

    assert first == 1
    assert second == 0
    assert len(poster.posts) == 1


async def test_handle_ignores_text_without_shopee_link(tmp_path):
    poster = _FakePoster()
    pipeline = _pipeline(tmp_path, poster, _sample_product())

    count = await pipeline.handle("Bom dia, sem ofertas hoje")

    assert count == 0
    assert poster.posts == []
