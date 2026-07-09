from src.channel_poster import ChannelPoster


class _FakeTelethonClient:
    def __init__(self):
        self.calls = []
        self.text_calls = []

    async def send_file(self, channel, file, caption=None):
        self.calls.append({"channel": channel, "file": file, "caption": caption})

    async def send_message(self, channel, text, link_preview):
        self.text_calls.append(
            {"channel": channel, "text": text, "link_preview": link_preview}
        )


async def test_post_sends_file_with_caption():
    client = _FakeTelethonClient()
    poster = ChannelPoster(client, channel="@ofertas_lanny")
    await poster.post("https://example.com/img.jpg", "texto del post")

    assert client.calls == [
        {
            "channel": "@ofertas_lanny",
            "file": "https://example.com/img.jpg",
            "caption": "texto del post",
        }
    ]


async def test_post_text_sends_message_with_link_preview():
    client = _FakeTelethonClient()
    poster = ChannelPoster(client, channel="@ofertas_lanny")
    await poster.post_text("texto del post de Amazon")

    assert client.text_calls == [
        {
            "channel": "@ofertas_lanny",
            "text": "texto del post de Amazon",
            "link_preview": True,
        }
    ]


async def test_post_falls_back_to_separate_message_when_caption_too_long():
    """Telegram corta los captions a 1024 chars: mejor foto + mensaje que texto perdido."""
    client = _FakeTelethonClient()
    poster = ChannelPoster(client, channel="@ofertas_lanny")
    largo = "x" * (ChannelPoster.CAPTION_LIMIT + 1)

    await poster.post("https://example.com/img.jpg", largo)

    assert client.calls == [
        {"channel": "@ofertas_lanny", "file": "https://example.com/img.jpg", "caption": None}
    ]
    assert client.text_calls[0]["text"] == largo


async def test_post_keeps_caption_at_the_limit():
    client = _FakeTelethonClient()
    poster = ChannelPoster(client, channel="@ofertas_lanny")
    justo = "x" * ChannelPoster.CAPTION_LIMIT

    await poster.post("https://example.com/img.jpg", justo)

    assert client.calls[0]["caption"] == justo
    assert client.text_calls == []


class FloodWaitError(Exception):
    """Imita a telethon.errors.FloodWaitError: se detecta por nombre de clase."""

    def __init__(self, seconds):
        super().__init__(f"wait {seconds}")
        self.seconds = seconds


class _FloodingClient(_FakeTelethonClient):
    """Lanza FloodWait las primeras `fails` veces, después funciona."""

    def __init__(self, fails, seconds=3):
        super().__init__()
        self.fails = fails
        self.seconds = seconds

    async def send_message(self, channel, text, link_preview):
        if self.fails:
            self.fails -= 1
            raise FloodWaitError(self.seconds)
        await super().send_message(channel, text, link_preview)


async def test_post_text_waits_and_retries_on_flood_wait():
    client = _FloodingClient(fails=1, seconds=3)
    slept = []
    poster = ChannelPoster(client, channel="@c", sleep=lambda s: _record(slept, s))

    await poster.post_text("oferta")

    assert client.text_calls[0]["text"] == "oferta"
    assert slept == [4]  # los 3s que pidió Telegram + 1 de colchón


async def test_post_text_gives_up_after_max_retries():
    client = _FloodingClient(fails=99, seconds=3)
    poster = ChannelPoster(client, channel="@c", sleep=lambda s: _record([], s))

    try:
        await poster.post_text("oferta")
    except FloodWaitError:
        pass
    else:
        raise AssertionError("debía propagar el FloodWait tras agotar los reintentos")
    assert client.text_calls == []


async def test_flood_wait_longer_than_the_cap_is_not_awaited():
    """Bloquear el bot media hora es peor que perder una oferta."""
    client = _FloodingClient(fails=1, seconds=ChannelPoster.MAX_WAIT_SECONDS + 1)
    slept = []
    poster = ChannelPoster(client, channel="@c", sleep=lambda s: _record(slept, s))

    try:
        await poster.post_text("oferta")
    except FloodWaitError:
        pass
    else:
        raise AssertionError("debía propagar sin esperar")
    assert slept == []


async def test_other_errors_are_not_retried():
    class _Broken(_FakeTelethonClient):
        async def send_message(self, channel, text, link_preview):
            raise RuntimeError("sesión caída")

    poster = ChannelPoster(_Broken(), channel="@c")
    try:
        await poster.post_text("oferta")
    except RuntimeError:
        pass
    else:
        raise AssertionError("un error que no es FloodWait debe propagar sin reintentar")


async def _record(bucket, seconds):
    bucket.append(seconds)
