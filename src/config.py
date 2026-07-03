import os
from typing import List

from dotenv import load_dotenv


def load_config() -> dict:
    """Carga configuración desde .env (secretos) y variables con defaults."""
    load_dotenv()

    def _chats(raw: str) -> List:
        parsed = []
        for token in (raw or "").split(","):
            token = token.strip()
            if not token:
                continue
            parsed.append(int(token) if token.lstrip("-").isdigit() else token)
        return parsed

    return {
        "api_id": os.getenv("TELEGRAM_API_ID"),
        "api_hash": os.getenv("TELEGRAM_API_HASH"),
        "shopee_app_id": os.getenv("SHOPEE_APP_ID"),
        "shopee_secret": os.getenv("SHOPEE_SECRET"),
        "channel_id": os.getenv("TARGET_CHANNEL_ID"),
        "source_chats": _chats(os.getenv("SOURCE_CHATS", "")),
        "dedup_db": os.getenv("DEDUP_DB", "dedup.db"),
        "hooks_file": os.getenv("HOOKS_FILE", "hooks.txt"),
    }
