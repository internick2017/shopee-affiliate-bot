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
