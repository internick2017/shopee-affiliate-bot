"""
telegram_listener.py — Telegram USER-account listener via Telethon.

Why Telethon instead of a bot token?
-------------------------------------
The source group is a private group the user is a member of, but cannot add
a bot to.  Telethon logs in as the user's own Telegram account (phone +
one-time code), so it can read messages from any group the user has joined.
No bot needs to be added to the group.

Lazy import
-----------
``telethon`` is an optional dependency.  All real network/Telegram code lives
inside ``TelethonListener.start()`` and is imported there.  The rest of the
module (including ``should_process``) is pure Python and testable without
telethon installed.

Setup (first run)
-----------------
1. Get a free API ID + API hash at https://my.telegram.org (login → API
   development tools → Create application).
2. Export them::

       export TELEGRAM_API_ID=12345678
       export TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890

3. Run the bot once.  Telethon will prompt for your phone number and the
   one-time code Telegram sends.  After that a ``shopee_user_session.string``
   file is written and subsequent runs are automatic.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional, Sequence

logger = logging.getLogger(__name__)


@dataclass
class TelethonConfig:
    api_id_env: str = "TELEGRAM_API_ID"
    api_hash_env: str = "TELEGRAM_API_HASH"
    session_name: str = "shopee_user_session"
    # Only process messages from these chat IDs or usernames (empty = all).
    allowed_chats: Sequence = field(default_factory=tuple)
    # Diagnostic mode: log EVERY incoming message (chat title + text preview)
    # before filtering. Confirms the integration is alive and reveals exact
    # group names/IDs so you can add more groups to allowed_chats.
    observe: bool = False
    # When set (and observe=True), append messages as one JSON line to this
    # file (full text + chat + timestamp) for multi-day review. Survives restarts.
    observe_file: Optional[str] = None
    # If True, the observe_file only records IN-SCOPE messages (the source
    # group(s) we actually care about), skipping unrelated chats. Keeps the
    # log focused on the relevant chats so we can audit why processing failed.
    # The console [OBSERVE] line still shows every message regardless.
    observe_file_in_scope_only: bool = True


def _append_observation(path, *, chat_id, chat_title, in_scope, text, ts=None) -> None:
    """Append one observed message as a JSON line (for multi-day review).
    Best-effort: never raises (observation logging must not crash the bot)."""
    import json
    import os
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        record = {
            "ts": ts.isoformat() if hasattr(ts, "isoformat") else None,
            "chat_id": chat_id,
            "chat_title": chat_title,
            "in_scope": in_scope,
            "text": text,
        }
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Could not write observation to %s: %s", path, exc)


def should_process(chat_id, chat_title, allowed_chats) -> bool:
    """Pure, testable: decide whether a message from this chat is in scope.

    Empty ``allowed_chats`` -> process everything.  Otherwise match
    ``chat_id`` (int) OR ``chat_title``/username (str, case-insensitive
    substring).
    """
    if not allowed_chats:
        return True
    for a in allowed_chats:
        if isinstance(a, int) and chat_id == a:
            return True
        if isinstance(a, str) and chat_title and a.lower() in chat_title.lower():
            return True
    return False


class TelethonListener:
    """Reads messages from the user's Telegram account via Telethon and routes
    each message's text to an async handler.  Real telethon import is lazy."""

    def __init__(
        self,
        config: TelethonConfig,
        on_text: Callable[[str, Optional[str]], Awaitable[None]],
    ) -> None:
        self.config = config
        self.on_text = on_text
        self._client = None

    async def start(self) -> None:
        import os
        from telethon import TelegramClient, events  # lazy
        from telethon.sessions import StringSession

        api_id = os.getenv(self.config.api_id_env)
        api_hash = os.getenv(self.config.api_hash_env)
        if not api_id or not api_hash:
            raise RuntimeError(
                f"Set {self.config.api_id_env} and {self.config.api_hash_env} "
                "(get them free at https://my.telegram.org)."
            )

        # Use StringSession to avoid SQLite file-locking issues on Windows.
        # The session string is persisted to a plain-text file alongside the
        # old .session file.  This is re-entrant-safe and survives restarts.
        session_file = self.config.session_name + ".string"
        session_string = ""
        if os.path.exists(session_file):
            try:
                with open(session_file, "r", encoding="utf-8") as fh:
                    session_string = fh.read().strip()
            except Exception as exc:
                logger.warning("Could not read session file %s: %s", session_file, exc)

        self._session_file = session_file
        self._client = TelegramClient(
            StringSession(session_string), int(api_id), api_hash
        )

        @self._client.on(events.NewMessage)
        async def _handler(event):  # pragma: no cover - requires live telegram
            try:
                msg = event.message
                text = msg.message or ""
                if not text:
                    return
                chat = await event.get_chat()
                chat_id = getattr(chat, "id", None)
                chat_title = (
                    getattr(chat, "title", None)
                    or getattr(chat, "username", None)
                )
                in_scope = should_process(
                    chat_id, chat_title, self.config.allowed_chats
                )
                if self.config.observe:
                    preview = text.replace("\n", " ⏎ ")[:120]
                    logger.info(
                        "[OBSERVE] chat=%r id=%s in_scope=%s | %s",
                        chat_title, chat_id, in_scope, preview,
                    )
                    if self.config.observe_file and (
                        in_scope or not self.config.observe_file_in_scope_only
                    ):
                        _append_observation(
                            self.config.observe_file,
                            chat_id=chat_id, chat_title=chat_title,
                            in_scope=in_scope, text=text,
                            ts=getattr(msg, "date", None),
                        )
                if not in_scope:
                    return
                # Pass chat_title so the pipeline can decide how to handle the
                # message based on its source chat, and the photo so the post sale
                # ilustrado: los canales fuente siempre postean con imagen, y
                # reenviarla por referencia evita descargarla y volverla a subir.
                await self.on_text(text, chat_title, photo=getattr(msg, "photo", None))
            except Exception as exc:
                logger.error(
                    "Telethon handler error: %s", exc, exc_info=True
                )

        await self._client.start()  # interactive first run: prompts phone + code

        # Persist the session string so the next run doesn't need a login.
        try:
            saved = self._client.session.save()
            with open(self._session_file, "w", encoding="utf-8") as fh:
                fh.write(saved)
            logger.info("Session saved to %s", self._session_file)
        except Exception as exc:
            logger.warning("Could not save session string: %s", exc)

        logger.info(
            "Telethon listener started (reading as your user account)."
        )

    async def notify(self, text: str) -> None:
        """Send a message to the user's own Telegram 'Saved Messages' (the 'me'
        chat), so events show up on the user's phone instantly. Best-effort:
        never raises — a failed notification must not affect the pipeline."""
        if self._client is None:
            return
        try:
            await self._client.send_message("me", text)
        except Exception as exc:  # pragma: no cover - network/telegram errors
            logger.warning("Could not send Telegram notification: %s", exc)

    async def run_until_disconnected(self) -> None:
        if self._client is not None:
            await self._client.run_until_disconnected()

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
            logger.info("Telethon listener stopped.")
