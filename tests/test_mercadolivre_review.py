import asyncio

from src.mercadolivre_review import (
    DEFAULT_MARKER,
    MercadoLivreReviewPipeline,
    build_mercadolivre_auto_post,
    build_mercadolivre_review_message,
    has_mercadolivre_links,
    mercadolivre_dedup_key,
)
from tests.fakes import FakeDedup

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


# Mismo body real usado en tests/test_mercadolivre_resolver.py (Smart TV Hisense,
# item_id MLB54629493) — PROMOCASINHA_ML de arriba trae justo ese meli.la/1Q8EMBW.
_PRODUCT_BODY = (
    '<html><head>'
    '<meta property="og:title" content="Smart Tv Hisense De 65 Polegadas Vidaa 65u6qv Uled 4k"/>'
    '</head><body><script>window.__PRELOADED_STATE__={"melidataSocial":{'
    '"path":"/affiliates/profile","type":"view","should_ignore_stream":false,'
    '"event_data":{"page_type":"affiliate-profile","content_id":"not_apply",'
    '"item_id":"MLB54629493","owner_id":"2530242411","matt_tool":"70340356",'
    '"source":"affiliate-profile"}}}</script></body></html>'
)

_LIST_BODY = (
    '<html><head>'
    '<meta property="og:title" content="Minhas listas de recomendações"/>'
    '</head><body><script>window.__PRELOADED_STATE__={"page_type":"lists"}'
    '</script></body></html>'
)


class _FakeMlResponse:
    def __init__(self, text):
        self.text = text

    def close(self):
        pass


def _fake_ml_get(body):
    def get(url, **kwargs):
        return _FakeMlResponse(body)

    return get


def test_auto_post_replaces_link_and_has_no_marker():
    msg = build_mercadolivre_auto_post(
        PROMOCASINHA_ML, "lannybot", "56889681", http_get=_fake_ml_get(_PRODUCT_BODY)
    )
    assert msg is not None
    assert not msg.startswith(DEFAULT_MARKER)
    assert "⚠️" not in msg
    assert (
        "https://www.mercadolivre.com.br/p/MLB54629493"
        "?matt_word=lannybot&matt_tool=56889681"
    ) in msg
    assert "https://meli.la/1Q8EMBW" not in msg
    # el resto del contenido sigue ahí
    assert "Smart TV Hisense de 65 polegadas Vidaa 65u6qv Uled 4k" in msg
    assert "TVCASASBAHIA" in msg


def test_auto_post_none_when_resolution_fails():
    msg = build_mercadolivre_auto_post(
        PROMOCASINHA_ML, "lannybot", "56889681", http_get=_fake_ml_get(_LIST_BODY)
    )
    assert msg is None


def test_auto_post_none_without_ml_links():
    assert (
        build_mercadolivre_auto_post(
            "sem mercado livre aqui", "lannybot", "56889681",
            http_get=_fake_ml_get(_PRODUCT_BODY),
        )
        is None
    )


def test_auto_post_strips_competitor_footer():
    text = (
        "Produto X\n"
        "https://meli.la/1Q8EMBW\n"
        "🛍 Grupos de promos:\n"
        "https://ctlinks.com.br"
    )
    msg = build_mercadolivre_auto_post(
        text, "lannybot", "56889681", http_get=_fake_ml_get(_PRODUCT_BODY)
    )
    assert msg is not None
    assert "ctlinks.com.br" not in msg
    assert "Grupos de promos" not in msg


def test_pipeline_auto_posts_when_configured_and_resolvable():
    poster = FakePoster()
    pipe = MercadoLivreReviewPipeline(
        poster, matt_word="lannybot", matt_tool="56889681"
    )

    import src.mercadolivre_review as module

    original = module.build_own_mercadolivre_links

    def fake_build_own(text, matt_word, matt_tool, **kwargs):
        assert matt_word == "lannybot"
        assert matt_tool == "56889681"
        return {
            "https://meli.la/1Q8EMBW": (
                "https://www.mercadolivre.com.br/p/MLB54629493"
                "?matt_word=lannybot&matt_tool=56889681"
            )
        }

    module.build_own_mercadolivre_links = fake_build_own
    try:
        result = asyncio.run(pipe.handle(PROMOCASINHA_ML))
    finally:
        module.build_own_mercadolivre_links = original

    assert result == 1
    assert len(poster.posts) == 1
    assert not poster.posts[0].startswith(DEFAULT_MARKER)
    assert "MLB54629493" in poster.posts[0]


def test_pipeline_auto_path_skips_duplicate():
    """Mismo caso que test_pipeline_skips_duplicate, pero para la rama automática:
    handle() también reserva la clave de dedup antes de postear el link propio
    (lógica duplicada a propósito de ReviewPipeline.handle, ver MercadoLivreReviewPipeline)."""
    poster = FakePoster()
    pipe = MercadoLivreReviewPipeline(
        poster, matt_word="lannybot", matt_tool="56889681", dedup=FakeDedup()
    )

    import src.mercadolivre_review as module

    original = module.build_own_mercadolivre_links

    def fake_build_own(text, matt_word, matt_tool, **kwargs):
        return {
            "https://meli.la/1Q8EMBW": (
                "https://www.mercadolivre.com.br/p/MLB54629493"
                "?matt_word=lannybot&matt_tool=56889681"
            )
        }

    module.build_own_mercadolivre_links = fake_build_own
    try:
        assert asyncio.run(pipe.handle(PROMOCASINHA_ML)) == 1
        assert asyncio.run(pipe.handle(PROMOCASINHA_ML)) == 1
    finally:
        module.build_own_mercadolivre_links = original

    assert len(poster.posts) == 1


def test_pipeline_falls_back_to_manual_when_not_resolvable():
    poster = FakePoster()
    pipe = MercadoLivreReviewPipeline(
        poster, matt_word="lannybot", matt_tool="56889681"
    )

    import src.mercadolivre_review as module

    original = module.build_own_mercadolivre_links
    module.build_own_mercadolivre_links = lambda *a, **k: None
    try:
        result = asyncio.run(pipe.handle(PROMOCASINHA_ML))
    finally:
        module.build_own_mercadolivre_links = original

    assert result == 1
    assert len(poster.posts) == 1
    assert poster.posts[0].startswith(DEFAULT_MARKER)


def test_pipeline_without_matt_credentials_behaves_like_before():
    """Sin matt_word/matt_tool configurados, el camino automático ni se intenta:
    cero regresión respecto al comportamiento anterior a este feature."""
    poster = FakePoster()
    pipe = MercadoLivreReviewPipeline(poster)

    result = asyncio.run(pipe.handle(PROMOCASINHA_ML))

    assert result == 1
    assert poster.posts[0].startswith(DEFAULT_MARKER)


def test_pipeline_skips_auto_thread_without_ml_shortlinks():
    """Con matt_word/matt_tool configurados pero sin shortlinks meli.la en el texto,
    ni se spawnea el thread de resolución (mismo patrón que
    AmazonPipeline._expanded con has_amazon_shortlinks): build_mercadolivre_auto_post
    no debería llamarse."""
    poster = FakePoster()
    pipe = MercadoLivreReviewPipeline(
        poster, matt_word="lannybot", matt_tool="56889681"
    )

    import src.mercadolivre_review as module

    def boom(*args, **kwargs):
        raise AssertionError(
            "build_mercadolivre_auto_post no debería llamarse sin shortlinks de ML"
        )

    original = module.build_mercadolivre_auto_post
    module.build_mercadolivre_auto_post = boom
    try:
        result = asyncio.run(pipe.handle("https://www.amazon.com.br/dp/X"))
    finally:
        module.build_mercadolivre_auto_post = original

    assert result == 0
    assert poster.posts == []
