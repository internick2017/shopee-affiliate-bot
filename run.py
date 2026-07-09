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

    # Holder for the shared pipeline: on_text is wired into the listener at
    # construction time, but the pipeline needs the authenticated Telethon
    # client, which only exists after listener.start() returns. The closure
    # below reads pipeline_holder["pipeline"] lazily on each call, so it's
    # safe as long as we populate it before any awaited code can dispatch a
    # queued message (see note below).
    pipeline_holder = {}

    async def on_text(text, chat_title=None, photo=None):
        # El pipeline viejo de Shopee arma su propio post con la imagen que devuelve
        # la API, así que ignora la foto del mensaje original.
        pipeline = pipeline_holder.get("pipeline")
        if pipeline is None:
            return
        await pipeline.handle(text, chat_title)

    tel_cfg = TelethonConfig(
        session_name="shopee_user_session",
        allowed_chats=tuple(cfg["source_chats"]),
        observe=observe,
    )
    listener = TelethonListener(tel_cfg, on_text)
    await listener.start()

    # Build every stateful component ONCE and reuse it for the life of the
    # process, instead of rebuilding them per message:
    # - DedupStore opens a SQLite connection that is never closed otherwise
    #   (a fresh one per message leaks connections/file handles over time).
    # - HookBank tracks the last hook shown to avoid consecutive repeats;
    #   rebuilding it per message resets that state every time.
    # - hooks.txt is only read from disk once instead of on every message.
    # No `await` happens between listener._client becoming available and
    # pipeline_holder being populated, so under asyncio's single-threaded
    # event loop no queued message can be dispatched to on_text before the
    # pipeline is assigned.
    poster = ChannelPoster(listener._client, cfg["channel_id"])
    pipeline_holder["pipeline"] = Pipeline(
        extractor=extract_shopee_links,
        resolver=lambda url: resolve_shortlink(url),
        dedup=DedupStore(cfg["dedup_db"]),
        client=client,
        hookbank=HookBank.from_file(cfg["hooks_file"]),
        poster=poster,
    )

    logger.info("Escuchando Telegram... (observe=%s)", observe)
    await listener.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
