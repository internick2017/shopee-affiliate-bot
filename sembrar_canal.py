"""sembrar_canal.py — postea al canal destino las ofertas de Amazon de los
últimos N mensajes del canal fuente (para tener contenido inicial).

Uso:
    python sembrar_canal.py [N]     (N por defecto = 10)

- Reusa la sesión `shopee_user_session` del bot. El bot de ofertas debe estar
  DETENIDO al correr esto, para no chocar con la misma sesión.
- Lee AMAZON_TAG, SOURCE_CHATS y TARGET_CHANNEL_ID del .env (igual que el bot).
- Solo postea las ofertas de Amazon (las de Mercado Livre se saltean).
- Corre una vez y termina.
"""
from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

from src.lanny_post import build_lanny_amazon_post
from src.post_builder import HookBank

SESSION_FILE = "shopee_user_session.string"


def _is_numeric(s: str) -> bool:
    return bool(s) and s.lstrip("-").isdigit()


async def main() -> None:
    load_dotenv()
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    tag = os.getenv("AMAZON_TAG")
    source = (os.getenv("SOURCE_CHATS") or "Crowman").split(",")[0].strip()
    target = os.getenv("TARGET_CHANNEL_ID")
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10

    if not (api_id and api_hash and tag and target):
        print("Falta TELEGRAM_API_ID/HASH, AMAZON_TAG o TARGET_CHANNEL_ID en .env")
        return

    from telethon import TelegramClient
    from telethon.sessions import StringSession

    session_string = ""
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r", encoding="utf-8") as fh:
            session_string = fh.read().strip()

    client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
    await client.start()

    source_entity = None
    target_entity = None
    async for d in client.iter_dialogs():
        name = (d.name or "").lower()
        if source_entity is None and source.lower() in name:
            source_entity = d.entity
        if target_entity is None:
            if _is_numeric(target) and d.id == int(target):
                target_entity = d.entity
            elif not _is_numeric(target) and target.lower() in name:
                target_entity = d.entity

    if source_entity is None:
        print(f"No encontré el canal fuente que contenga '{source}'.")
        await client.disconnect()
        return
    if target_entity is None:
        print(f"No encontré el canal destino '{target}'.")
        await client.disconnect()
        return

    hookbank = HookBank.from_file(os.getenv("HOOKS_FILE", "hooks.txt"))

    messages = await client.get_messages(source_entity, limit=n)
    posted = 0
    skipped = 0
    for m in reversed(messages):  # más viejos primero, para orden cronológico
        text = m.message or ""
        post = build_lanny_amazon_post(text, tag, hookbank.next())
        if post:
            await client.send_message(target_entity, post, link_preview=True)
            posted += 1
        else:
            skipped += 1

    print(f"Revisados {len(messages)} mensajes. Posteadas {posted} ofertas de Amazon "
          f"al canal; {skipped} salteados (Mercado Livre / sin Amazon).")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
