"""fetch_mensajes.py — baja los últimos mensajes de un canal de Telegram a un archivo.

Herramienta de un solo uso para juntar mensajes reales (p. ej. del canal de
ofertas de Mercado Livre) y con eso diseñar el extractor de nombres de producto.

Uso:
    python fetch_mensajes.py "Crowman" 40
      arg1 = parte del nombre del canal (o @username). Default: "Crowman"
      arg2 = cuántos mensajes bajar. Default: 40

- Reusa TELEGRAM_API_ID / TELEGRAM_API_HASH del .env (los mismos del bot de trading).
- Usa su PROPIA sesión ('fetch_session'), no toca la del bot de trading ni la del
  bot de Shopee, así no desconecta nada.
- La primera corrida pide teléfono + código (una sola vez).
- Escribe los mensajes a 'mensajes_<query>.txt' en esta carpeta. NO postea nada.
"""
from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

SESSION_FILE = "fetch_session.string"


async def main() -> None:
    load_dotenv()
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    if not api_id or not api_hash:
        print("Falta TELEGRAM_API_ID / TELEGRAM_API_HASH en el .env.")
        print("Copiá .env.example a .env y poné los mismos valores del bot de trading.")
        return

    from telethon import TelegramClient  # lazy import
    from telethon.sessions import StringSession

    query = sys.argv[1] if len(sys.argv) > 1 else "Crowman"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 40

    session_string = ""
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, encoding="utf-8") as fh:
            session_string = fh.read().strip()

    client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
    await client.start()  # primera vez: pide teléfono + código

    with open(SESSION_FILE, "w", encoding="utf-8") as fh:
        fh.write(client.session.save())

    target = None
    async for dialog in client.iter_dialogs():
        if query.lower() in (dialog.name or "").lower():
            target = dialog
            break

    if target is None:
        print(f"No encontré ningún chat/canal que contenga '{query}' en el nombre.")
        print("Probá con otra parte del nombre, p. ej. python fetch_mensajes.py Promo")
        await client.disconnect()
        return

    out_path = f"mensajes_{query}.txt"
    count = 0
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(f"Canal: {target.name} (id {target.id})\n\n")
        async for msg in client.iter_messages(target.id, limit=limit):
            text = msg.message or ""
            if not text.strip():
                continue
            count += 1
            fh.write("===== MENSAJE =====\n")
            fh.write(text.strip() + "\n\n")

    print(f"Canal: {target.name}")
    print(f"Guardé {count} mensajes en: {out_path}")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
