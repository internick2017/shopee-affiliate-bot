"""Entry point: modo Amazon — escucha Telegram y publica ofertas de Amazon con el
tag de afiliado del owner en el canal privado.

Uso:
    python run_amazon.py            # corre el pipeline
    python run_amazon.py --observe  # modo diagnóstico: loguea cada mensaje y su chat_id

Requiere AMAZON_TAG en el .env (tu tag de afiliado de Amazon). Sin eso el bot
no puede armar posts monetizados, así que no arranca.
"""
import asyncio
import logging
import sys

from src.amazon_pipeline import AmazonPipeline
from src.channel_poster import ChannelPoster
from src.config import load_config
from src.telegram_listener import TelethonConfig, TelethonListener

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("amazon-bot")


def _is_numeric(value) -> bool:
    """True if value is an int, or a string of digits (optionally with a leading '-')."""
    if isinstance(value, int):
        return True
    if isinstance(value, str):
        stripped = value.lstrip("-")
        return bool(stripped) and stripped.isdigit()
    return False


async def _resolve_target(listener, target):
    """Numeric targets (int or numeric string) are used directly. A non-numeric
    string is treated as a channel NAME: scan the user's dialogs and return the
    id of the first one whose name contains it (case-insensitive). Returns None
    if a name target can't be matched to any dialog."""
    if _is_numeric(target):
        return int(target)

    async for dialog in listener._client.iter_dialogs():
        name = getattr(dialog, "name", None)
        if name and target.lower() in name.lower():
            return dialog.id
    return None


async def main() -> None:
    observe = "--observe" in sys.argv
    cfg = load_config()

    if not cfg["amazon_tag"]:
        logger.error(
            "Falta AMAZON_TAG en el .env: no se puede correr el bot de Amazon sin un tag de afiliado."
        )
        return

    if not cfg["channel_id"]:
        logger.error("Falta TARGET_CHANNEL_ID en el .env.")
        return

    # Holder for the shared pipeline: on_text is wired into the listener at
    # construction time, but the pipeline needs the authenticated Telethon
    # client (and the resolved target channel), which only exist after
    # listener.start() returns. Same pattern as run.py.
    pipeline_holder = {}

    async def on_text(text, chat_title=None):
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

    target = await _resolve_target(listener, cfg["channel_id"])
    if target is None:
        logger.error(
            "No se encontró ningún canal cuyo nombre contenga %r. Revisa TARGET_CHANNEL_ID.",
            cfg["channel_id"],
        )
        return

    # Build the pipeline ONCE and reuse it for the life of the process, same
    # rationale as run.py: avoid rebuilding stateful components per message.
    # No `await` happens between resolving `target` and populating
    # pipeline_holder, so no queued message can reach on_text before the
    # pipeline is assigned.
    poster = ChannelPoster(listener._client, target)
    pipeline_holder["pipeline"] = AmazonPipeline(cfg["amazon_tag"], poster)

    logger.info(
        "Bot Amazon listo. tag=%s source_chats=%s target=%s (observe=%s)",
        cfg["amazon_tag"], cfg["source_chats"], target, observe,
    )
    logger.info("Escuchando Telegram... (observe=%s)", observe)
    await listener.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
