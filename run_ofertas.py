"""Entry point: bot de ofertas — escucha Telegram y publica ofertas a canales privados.

Multi-fuente: enruta cada mensaje por OfferPipeline, que prueba los handlers en orden
y usa el primero que lo reclame:

    Amazon         -> re-taguea el link y arma el post estilo Lanny (automático)
    Shopee         -> post propio con datos reales si hay credenciales y descuento comprobable; si no, reenvía marcado
    Mercado Livre  -> reenvía marcado, para generar el link a mano

Cada plataforma publica en su propio canal, y el post lleva la foto del mensaje original.
Un mensaje que ningún handler reclama se descarta.

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
from src.channel_poster import ChannelPoster
from src.config import load_config
from src.dedup_store import DedupStore
from src.image_watermark import strip_watermark_from_media
from src.mercadolivre_review import MercadoLivreReviewPipeline
from src.offer_pipeline import OfferPipeline
from src.post_builder import HookBank
from src.shopee_review import ShopeeReviewPipeline
from src.telegram_listener import TelethonConfig, TelethonListener

# Única fuente conocida hoy que pega un watermark de marca en sus fotos (verificado
# 2026-08-01, ver src/image_watermark.py). Si mañana aparece otra, sumarla acá.
_WATERMARKED_SOURCES = ("promocasinha",)

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


# Distingue "el canal está configurado pero no existe" (abortar) de un id de canal
# válido. No sirve None: un id de canal nunca es None, pero `_resolve_target`
# devuelve None justamente cuando no encuentra el canal.
_UNRESOLVED = object()


async def _resolve_platform_channel(listener, configured, fallback, env_var, platform):
    """Resuelve el canal de una plataforma de reenvío manual.

    Sin configurar -> cae al canal principal con un warning (no perder mensajes).
    Configurado pero inexistente -> `_UNRESOLVED`, y el bot no arranca: mandar las
    ofertas al canal equivocado en silencio sería peor que fallar.
    """
    if not configured:
        logger.warning(
            "%s no está seteado: las ofertas de %s irán al canal principal.",
            env_var,
            platform,
        )
        return fallback

    target = await _resolve_target(listener, configured)
    if target is None:
        logger.error(
            "No se encontró ningún canal cuyo nombre contenga %r. Revisa %s.",
            configured,
            env_var,
        )
        return _UNRESOLVED
    return target


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
    # listener.start() returns.
    pipeline_holder = {}

    async def on_text(text, chat_title=None, photo=None):
        pipeline = pipeline_holder.get("pipeline")
        if pipeline is None:
            return
        if (
            photo is not None
            and chat_title
            and any(source in chat_title.lower() for source in _WATERMARKED_SOURCES)
        ):
            photo = await strip_watermark_from_media(listener._client, photo)
        await pipeline.handle(text, chat_title, photo=photo)

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

    # Cada plataforma de reenvío manual publica en su propio canal.
    shopee_target = await _resolve_platform_channel(
        listener, cfg["shopee_channel_id"], amazon_target, "SHOPEE_CHANNEL_ID", "Shopee"
    )
    if shopee_target is _UNRESOLVED:
        return

    ml_target = await _resolve_platform_channel(
        listener, cfg["ml_channel_id"], amazon_target, "ML_CHANNEL_ID", "Mercado Livre"
    )
    if ml_target is _UNRESOLVED:
        return

    # Build the pipeline ONCE and reuse it for the life of the process:
    # avoid rebuilding stateful components per message.
    # Todos los `await` (resolución de canales) ya ocurrieron arriba; de acá a
    # poblar pipeline_holder no hay await, así que ningún mensaje encolado llega
    # a on_text antes de que el pipeline esté asignado.
    amazon_poster = ChannelPoster(listener._client, amazon_target)
    shopee_poster = ChannelPoster(listener._client, shopee_target)
    ml_poster = ChannelPoster(listener._client, ml_target)
    hookbank = HookBank.from_file(cfg["hooks_file"])
    # Un solo store compartido por todos los handlers: los grupos fuente se copian
    # ofertas entre sí, así que el mismo producto llega varias veces. Las claves
    # llevan prefijo de plataforma, así que no colisionan entre handlers.
    dedup = DedupStore(cfg["dedup_db"])
    expired = dedup.purge()
    if expired:
        logging.info("Dedup: %d claves vencidas purgadas", expired)
    amazon = AmazonPipeline(cfg["amazon_tag"], amazon_poster, hookbank, dedup=dedup)
    shopee_review = ShopeeReviewPipeline(
        shopee_poster,
        dedup=dedup,
        app_id=cfg["shopee_app_id"],
        secret=cfg["shopee_secret"],
        hooks=hookbank,
        umbral_comision=cfg["shopee_min_commission_pct"],
    )
    ml_review = MercadoLivreReviewPipeline(
        ml_poster,
        dedup=dedup,
        matt_word=cfg["ml_matt_word"],
        matt_tool=cfg["ml_matt_tool"],
        hooks=hookbank,
    )
    # Amazon primero: es el único que monetiza solo. Se rinde ante un mensaje con
    # links de Mercado Livre, así que esas ofertas caen al handler de ML.
    pipeline_holder["pipeline"] = OfferPipeline([amazon, shopee_review, ml_review])

    logger.info(
        "Bot de ofertas listo. amazon_tag=%s source_chats=%s amazon_channel=%s "
        "shopee_channel=%s ml_channel=%s dedup_db=%s (observe=%s)",
        cfg["amazon_tag"],
        cfg["source_chats"],
        amazon_target,
        shopee_target,
        ml_target,
        cfg["dedup_db"],
        observe,
    )
    logger.info("Escuchando Telegram... (observe=%s)", observe)
    await listener.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
