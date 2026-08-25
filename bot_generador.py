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
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.config import load_config
from src.post_builder import HookBank
from src.post_generator_bot import generate_post_reply
from src.user_credentials_store import UserCredentialsStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("bot-generador")

_MSG_SIN_ACCESO = "No tenés acceso a este bot. Hablá con el administrador."
_MSG_REGISTRO_OK = (
    "Listo, guardé tus credenciales. De ahora en más los posts van a llevar TU link "
    "de afiliado."
)
_MSG_REGISTRO_USO = (
    "Uso: /registrar_shopee <APP_ID> <SECRET>\n\n"
    "Sacá esos dos datos de tu panel de afiliados de Shopee "
    "(https://www.affiliateshopee.com.br). Sin registrar tus credenciales, el bot "
    "te arma el post igual, pero con el link que vos mandaste tal cual (no lo re-taguea)."
)
_MSG_BORRADO_OK = "Listo, borré tus credenciales. De ahora en más el link va a ser tal cual lo mandes."


def _check_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """None si tiene acceso; si no, ya le contestó "sin acceso" y el caller debe cortar."""
    cfg = context.bot_data["cfg"]
    user = update.effective_user
    if user is None or user.id not in cfg["bot_allowed_users"]:
        logger.info("Usuario sin acceso intentó usar el bot: %s", user.id if user else None)
        return None
    return user


async def _handle_registrar_shopee(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = _check_access(update, context)
    if user is None:
        await update.message.reply_text(_MSG_SIN_ACCESO)
        return

    if len(context.args) != 2:
        await update.message.reply_text(_MSG_REGISTRO_USO)
        return

    app_id, secret = context.args
    context.bot_data["credentials_store"].save(user.id, app_id, secret)
    logger.info("Usuario %s registró sus propias credenciales de Shopee", user.id)
    await update.message.reply_text(_MSG_REGISTRO_OK)


async def _handle_olvidar_shopee(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = _check_access(update, context)
    if user is None:
        await update.message.reply_text(_MSG_SIN_ACCESO)
        return

    context.bot_data["credentials_store"].remove(user.id)
    logger.info("Usuario %s borró sus credenciales de Shopee", user.id)
    await update.message.reply_text(_MSG_BORRADO_OK)


async def _handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.bot_data["cfg"]
    hooks = context.bot_data["hooks"]

    user = _check_access(update, context)
    if user is None:
        await update.message.reply_text(_MSG_SIN_ACCESO)
        return

    user_credentials = context.bot_data["credentials_store"].get(user.id)

    text = update.message.text or ""
    reply = generate_post_reply(
        text,
        cfg["shopee_app_id"],
        cfg["shopee_secret"],
        hooks,
        user_credentials=user_credentials,
    )

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
    application.bot_data["credentials_store"] = UserCredentialsStore(cfg["user_credentials_db"])

    application.add_handler(CommandHandler("registrar_shopee", _handle_registrar_shopee))
    application.add_handler(CommandHandler("olvidar_shopee", _handle_olvidar_shopee))
    application.add_handler(
        MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, _handle_message)
    )

    logger.info("Bot generador de posts listo. allowed_users=%s", cfg["bot_allowed_users"])
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
