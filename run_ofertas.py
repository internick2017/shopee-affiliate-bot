"""Entry point: bot de ofertas — escucha Telegram y publica ofertas al canal privado.

Multi-fuente: enruta cada mensaje por OfferPipeline. Hoy los handlers son Amazon
(retag + post estilo Lanny) y Shopee (reenvío a revisar); Mercado Livre se descarta.

Uso:
    python run_ofertas.py            # corre el pipeline
    python run_ofertas.py --observe  # modo diagnóstico: loguea cada mensaje y su chat_id

Requiere AMAZON_TAG en el .env porque el handler de Amazon es el que monetiza; sin
eso no arranca.
"""
import asyncio
import logging
import sys

from src.amazon_pipeline import AmazonPipeline
from src.offer_pipeline import OfferPipeline
from src.shopee_review import ShopeeReviewPipeline
from src.channel_poster import ChannelPoster
from src.config import load_config
from src.post_builder import HookBank
from src.telegram_listener import TelethonConfig, TelethonListener

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ofertas-bot")


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
            "Falta AMAZON_TAG en el .env: el handler de Amazon necesita tu tag de afiliado, así que el bot no arranca."
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

    amazon_target = await _resolve_target(listener, cfg["channel_id"])
    if amazon_target is None:
        logger.error(
            "No se encontró ningún canal cuyo nombre contenga %r. Revisa TARGET_CHANNEL_ID.",
            cfg["channel_id"],
        )
        return

    # Cada plataforma publica en su propio canal. Shopee -> "Ofertas Shopee"
    # (SHOPEE_CHANNEL_ID). Si no está configurado, cae al canal principal para
    # no perder los mensajes; si está pero no se resuelve, no arranca (evita
    # mandar Shopee al canal equivocado en silencio).
    shopee_target = amazon_target
    if cfg["shopee_channel_id"]:
        shopee_target = await _resolve_target(listener, cfg["shopee_channel_id"])
        if shopee_target is None:
            logger.error(
                "No se encontró ningún canal cuyo nombre contenga %r. Revisa SHOPEE_CHANNEL_ID.",
                cfg["shopee_channel_id"],
            )
            return
    else:
        logger.warning(
            "SHOPEE_CHANNEL_ID no está seteado: las ofertas de Shopee irán al canal principal (%r).",
            cfg["channel_id"],
        )

    # Build the pipeline ONCE and reuse it for the life of the process, same
    # rationale as run.py: avoid rebuilding stateful components per message.
    # Todos los `await` (resolución de canales) ya ocurrieron arriba; de acá a
    # poblar pipeline_holder no hay await, así que ningún mensaje encolado llega
    # a on_text antes de que el pipeline esté asignado.
    amazon_poster = ChannelPoster(listener._client, amazon_target)
    shopee_poster = ChannelPoster(listener._client, shopee_target)
    hookbank = HookBank.from_file(cfg["hooks_file"])
    amazon = AmazonPipeline(cfg["amazon_tag"], amazon_poster, hookbank)
    shopee_review = ShopeeReviewPipeline(shopee_poster)
    pipeline_holder["pipeline"] = OfferPipeline([amazon, shopee_review])

    logger.info(
        "Bot de ofertas listo. amazon_tag=%s source_chats=%s amazon_channel=%s shopee_channel=%s (observe=%s)",
        cfg["amazon_tag"], cfg["source_chats"], amazon_target, shopee_target, observe,
    )
    logger.info("Escuchando Telegram... (observe=%s)", observe)
    await listener.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
