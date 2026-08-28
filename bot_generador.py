"""Entry point: bot generador de posts — Telegram bot separado de run_ofertas.py.

Un usuario whitelisted le manda al bot, en chat privado:
  - un link de Shopee (afiliado o crudo) -> le contesta el post armado (foto + caption
    con link propio) para que lo publique a mano donde quiera;
  - `/video <link>` -> le contesta la imagen 9:16 de referencia para el generador de
    video, mas el prompt sugerido;
  - un archivo de video -> se lo devuelve reencuadrado a 1080x1920 para Shopee Video.

Uso:
    python bot_generador.py
"""

import io
import logging
import tempfile
from pathlib import Path

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.config import load_config
from src.post_builder import HookBank
from src.post_generator_bot import generate_post_reply, generate_video_reference
from src.product_ideas import CATEGORIAS, buscar_ideas, nombre_categoria
from src.sales_report import resumen_ventas
from src.user_credentials_store import UserCredentialsStore
from src.video_vertical import MODO_MARCO, MODO_RECORTE, to_vertical

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("bot-generador")

_MSG_SIN_ACCESO = "No tenés acceso a este bot. Hablá con el administrador."
_MSG_VIDEO_PESADO = (
    "Ese video pesa más de 20 MB y Telegram no me deja bajarlo. Mandalo más liviano "
    "o convertilo en la PC."
)
_MSG_VIDEO_FALLO = "No pude convertir ese video. Fijate que sea un MP4 válido."
_MSG_IDEAS_USO = (
    "Usá /ideas <categoría o palabra>.\n\n"
    "Categorías: {cats}\n\n"
    "O cualquier palabra suelta, por ejemplo: /ideas organizador cozinha"
)
_MSG_IDEAS_VACIO = "No encontré nada para eso. Probá otra palabra o una categoría."
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


async def _handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/video <link>` — devuelve la imagen 9:16 de referencia para el generador
    de video, más el prompt sugerido."""
    cfg = context.bot_data["cfg"]

    user = _check_access(update, context)
    if user is None:
        await update.message.reply_text(_MSG_SIN_ACCESO)
        return

    await update.message.reply_text("Armando la referencia vertical, dame unos segundos...")

    texto = update.message.text or ""
    # "nativo" al final = el generador ya produce 9:16 (Google Flow), no hace falta
    # componer para un recorte posterior.
    nativo = texto.strip().lower().endswith("nativo")

    ref = generate_video_reference(
        texto,
        cfg["shopee_app_id"],
        cfg["shopee_secret"],
        user_credentials=context.bot_data["credentials_store"].get(user.id),
        nativo=nativo,
    )

    if ref.error:
        await update.message.reply_text(ref.error)
        return

    # Como documento y no como foto: Telegram recomprime las fotos, y esta imagen
    # es el insumo de un generador de video — degradarla acá arruinaría el punto.
    await update.message.reply_document(
        document=io.BytesIO(ref.image_bytes),
        filename=ref.filename,
        caption=ref.caption[:1024],
    )
    # El prompt va aparte: no entra en un caption (tope 1024) y suelto se copia
    # de un toque en el celular.
    await update.message.reply_text(ref.prompt)

    # El link se guarda y se muestra: entre pedir la referencia y volver con el
    # video generado pasan minutos en otra app, y sin esto el link se pierde.
    if ref.link:
        context.bot_data.setdefault("ultimo_link", {})[user.id] = ref.link
        modo = "vertical nativo (Flow)" if nativo else "para reencuadrar despues"
        await update.message.reply_text(
            f"Prompt {modo}.\n\nLink del producto:\n{ref.link}",
            disable_web_page_preview=True,
        )


async def _handle_ventas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/ventas [dias]` — que se vendio de verdad con los links del canal.

    Es el contraste de `/ideas`: sin esto el ranking es una teoria que nunca se
    verifica contra la realidad."""
    cfg = context.bot_data["cfg"]

    user = _check_access(update, context)
    if user is None:
        await update.message.reply_text(_MSG_SIN_ACCESO)
        return

    dias = 30
    if context.args and context.args[0].isdigit():
        dias = max(1, min(int(context.args[0]), 180))

    await update.message.reply_text(f"Leyendo tus ventas de los ultimos {dias} dias...")

    app_id, secret = context.bot_data["credentials_store"].get(user.id) or (
        cfg["shopee_app_id"],
        cfg["shopee_secret"],
    )
    v = resumen_ventas(app_id, secret, dias=dias)
    if v.error:
        await update.message.reply_text(v.error)
        return
    if not v.completados:
        await update.message.reply_text(
            f"No hay ventas completadas en los ultimos {dias} dias."
        )
        return

    lineas = [
        f"<b>Ultimos {v.dias} dias</b>",
        f"Comision: <b>R$ {v.comision:.2f}</b> en {v.completados} ventas",
        f"Promedio por venta: R$ {v.por_venta:.2f}",
    ]
    if v.cancelados or v.pendientes:
        lineas.append(f"({v.cancelados} canceladas, {v.pendientes} pendientes, no contadas)")

    lineas.append("")
    lineas.append("<b>Por banda de precio</b>")
    for banda in v.bandas:
        lineas.append(
            f"{banda.etiqueta}: {banda.items} vendidos, "
            f"R$ {banda.comision:.2f} (R$ {banda.por_item:.2f} c/u)"
        )

    lineas.append("")
    lineas.append("<b>Los que mas dejaron</b>")
    for nombre, com in v.top:
        lineas.append(f"R$ {com:.2f} - {nombre}")

    await update.message.reply_text(
        "\n".join(lineas), parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )


async def _handle_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/ideas <categoría o palabra>` — qué conviene grabar, ranqueado.

    Usa las credenciales del usuario si las registró, para que los links que
    reciba sean suyos y no de la cuenta por defecto."""
    cfg = context.bot_data["cfg"]

    user = _check_access(update, context)
    if user is None:
        await update.message.reply_text(_MSG_SIN_ACCESO)
        return

    consulta = " ".join(context.args or []).strip()
    if not consulta:
        await update.message.reply_text(
            _MSG_IDEAS_USO.format(cats=", ".join(sorted(set(CATEGORIAS))))
        )
        return

    cat = nombre_categoria(consulta)
    donde = f"en {cat}" if cat else f"por \"{consulta}\""
    await update.message.reply_text(f"Buscando ideas {donde}...")

    app_id, secret = context.bot_data["credentials_store"].get(user.id) or (
        cfg["shopee_app_id"],
        cfg["shopee_secret"],
    )
    ideas = buscar_ideas(consulta, app_id, secret)
    if not ideas:
        await update.message.reply_text(_MSG_IDEAS_VACIO)
        return

    for n, idea in enumerate(ideas, 1):
        texto = (
            f"<b>{n}. {idea.titulo[:90]}</b>\n"
            f"R$ {idea.precio} - {idea.ventas} vendidos - "
            f"{idea.comision_pct:.0f}% comision - {idea.rating} estrellas\n"
            f"{idea.link}\n\n"
            f"<i>Referencia de video: /video {idea.link}</i>"
        )
        await update.message.reply_text(
            texto, parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )


async def _handle_video_vertical(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Recibe el video horizontal del generador y lo devuelve reencuadrado a 9:16.

    Se activa con cualquier video que le manden, sin comando: mandar el archivo ES
    la intención, y pedir además que escriban /convertir sería fricción al pedo."""
    if _check_access(update, context) is None:
        await update.message.reply_text(_MSG_SIN_ACCESO)
        return

    media = update.message.video or update.message.document
    # Los bots no pueden descargar archivos de más de 20 MB (límite de la Bot API).
    if (media.file_size or 0) > 20 * 1024 * 1024:
        await update.message.reply_text(_MSG_VIDEO_PESADO)
        return

    await update.message.reply_text("Reencuadrando a 9:16, dame unos segundos...")

    with tempfile.TemporaryDirectory() as tmp:
        entrada = Path(tmp) / "entrada.mp4"
        salida = Path(tmp) / "vertical.mp4"
        archivo = await context.bot.get_file(media.file_id)
        await archivo.download_to_drive(custom_path=str(entrada))

        # Los dos modos, para comparar con el mismo video y decidir con evidencia.
        variantes = [
            (MODO_RECORTE, "recorte", "pantalla completa, corta los costados"),
            (MODO_MARCO, "marco", "video entero, con fondo difuminado"),
        ]
        enviados = 0
        for modo, nombre, descripcion in variantes:
            destino = Path(tmp) / f"{nombre}.mp4"
            if not to_vertical(str(entrada), str(destino), modo=modo):
                continue
            await update.message.reply_document(
                document=destino.read_bytes(),
                filename=f"vertical-{nombre}.mp4",
                caption=f"{nombre.upper()}: {descripcion}",
            )
            enviados += 1

        if not enviados:
            await update.message.reply_text(_MSG_VIDEO_FALLO)
            return

        # Devolver el link del ultimo producto pedido: el usuario vuelve aca con
        # el video minutos despues y para entonces ya no lo tiene a mano.
        link = context.bot_data.get("ultimo_link", {}).get(update.effective_user.id)
        if link:
            await update.message.reply_text(
                f"Link del producto de tu ultima referencia:\n{link}",
                disable_web_page_preview=True,
            )


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
    application.add_handler(CommandHandler("video", _handle_video))
    application.add_handler(CommandHandler("ideas", _handle_ideas))
    application.add_handler(CommandHandler("ventas", _handle_ventas))
    application.add_handler(
        MessageHandler(
            (filters.VIDEO | filters.Document.VIDEO) & filters.ChatType.PRIVATE,
            _handle_video_vertical,
        )
    )
    application.add_handler(
        MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, _handle_message)
    )

    logger.info("Bot generador de posts listo. allowed_users=%s", cfg["bot_allowed_users"])
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
