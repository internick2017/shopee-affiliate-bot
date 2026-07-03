from src.channel_poster import ChannelPoster


class _FakeTelethonClient:
    def __init__(self):
        self.calls = []

    async def send_file(self, channel, file, caption):
        self.calls.append({"channel": channel, "file": file, "caption": caption})


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
