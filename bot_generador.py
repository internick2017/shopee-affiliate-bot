"""Entry point: bot generador de posts — Telegram bot separado de run_ofertas.py.

Un usuario whitelisted le manda al bot, en chat privado, un link de Shopee (afiliado
o crudo); el bot le contesta con el post ya armado (foto + caption con link propio)
para que lo publique a mano donde quiera.

Uso:
    python bot_generador.py
"""

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from src.config import load_config
from src.post_builder import HookBank
from src.post_generator_bot import generate_post_reply

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("bot-generador")

_MSG_SIN_ACCESO = "No tenés acceso a este bot. Hablá con el administrador."


async def _handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.bot_data["cfg"]
    hooks = context.bot_data["hooks"]

    user = update.effective_user
    if user is None or user.id not in cfg["bot_allowed_users"]:
        logger.info("Usuario sin acceso intentó usar el bot: %s", user.id if user else None)
        await update.message.reply_text(_MSG_SIN_ACCESO)
        return

    text = update.message.text or ""
    reply = generate_post_reply(text, cfg["shopee_app_id"], cfg["shopee_secret"], hooks)

    if reply.error:
        await update.message.reply_text(reply.error)
        return

    if reply.photo_url:
        await update.message.reply_photo(photo=reply.photo_url, caption=reply.caption)
    else:
        # Shopee no siempre trae imageUrl; degradar a solo texto en vez de fallar.
        await update.message.reply_text(reply.caption, parse_mode=ParseMode.HTML)


def main() -> None:
    cfg = load_config()

    if not cfg["telegram_bot_token"]:
        logger.error("Falta TELEGRAM_BOT_TOKEN en el .env: el bot no arranca.")
        return
    if not cfg["shopee_app_id"] or not cfg["shopee_secret"]:
        logger.error("Falta SHOPEE_APP_ID/SHOPEE_SECRET en el .env: el bot no arranca.")
        return
    if not cfg["bot_allowed_users"]:
        logger.warning(
            "BOT_ALLOWED_USERS está vacío: nadie va a poder usar el bot hasta que lo configures."
        )

    application = Application.builder().token(cfg["telegram_bot_token"]).build()
    application.bot_data["cfg"] = cfg
    application.bot_data["hooks"] = HookBank.from_file(cfg["hooks_file"])

    application.add_handler(
        MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, _handle_message)
    )

    logger.info("Bot generador de posts listo. allowed_users=%s", cfg["bot_allowed_users"])
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
