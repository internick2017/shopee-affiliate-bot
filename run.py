"""Entry point: escucha Telegram y entrega posts al canal.

Uso:
    python run.py            # corre el pipeline
    python run.py --observe  # modo diagnóstico: loguea cada mensaje y su chat_id

Si faltan las credenciales de Shopee, usa MockShopeeClient (datos de prueba),
así se puede validar todo el pipeline en Fase 2 sin el trámite.
"""
import asyncio
import logging
import sys

from src.channel_poster import ChannelPoster
from src.config import load_config
from src.dedup_store import DedupStore
from src.link_extractor import extract_shopee_links
from src.pipeline import Pipeline
from src.post_builder import HookBank
from src.shopee_client import MockShopeeClient, RealShopeeClient
from src.shortlink_resolver import resolve_shortlink
from src.telegram_listener import TelethonConfig, TelethonListener

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("shopee-bot")


async def main() -> None:
    observe = "--observe" in sys.argv
    cfg = load_config()

    if cfg["shopee_app_id"] and cfg["shopee_secret"]:
        client = RealShopeeClient(cfg["shopee_app_id"], cfg["shopee_secret"])
        logger.info("Usando RealShopeeClient (credenciales presentes).")
    else:
        client = MockShopeeClient()
        logger.warning("Sin credenciales Shopee: usando MockShopeeClient (datos de prueba).")

    listener_holder = {}

    async def on_text(text, chat_title=None):
        poster = ChannelPoster(listener_holder["client"], cfg["channel_id"])
        pipeline = Pipeline(
            extractor=extract_shopee_links,
            resolver=lambda url: resolve_shortlink(url),
            dedup=DedupStore(cfg["dedup_db"]),
            client=client,
            hookbank=HookBank.from_file(cfg["hooks_file"]),
            poster=poster,
        )
        await pipeline.handle(text, chat_title)

    tel_cfg = TelethonConfig(
        session_name="shopee_user_session",
        allowed_chats=tuple(cfg["source_chats"]),
        observe=observe,
    )
    listener = TelethonListener(tel_cfg, on_text)
    await listener.start()
    listener_holder["client"] = listener._client  # reusar la misma sesión para postear
    logger.info("Escuchando Telegram... (observe=%s)", observe)
    await listener.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
