from src.channel_poster import ChannelPoster


class _FakeTelethonClient:
    def __init__(self):
        self.calls = []
        self.text_calls = []

    async def send_file(self, channel, file, caption):
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
