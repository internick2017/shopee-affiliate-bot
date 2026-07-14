import os

from dotenv import load_dotenv


def _maybe_int(raw):
    """Coerce a numeric string (optionally leading '-') to int; else return as-is.

    Guards against malformed tokens like "--123" (passes the digit check after
    stripping leading dashes but is not a valid int): falls back to the raw
    value instead of raising.
    """
    if isinstance(raw, str) and raw and raw.lstrip("-").isdigit():
        try:
            return int(raw)
        except ValueError:
            return raw
    return raw


def load_config() -> dict:
    """Carga configuración desde .env (secretos) y variables con defaults."""
    load_dotenv()

    def _chats(raw: str) -> list:
        parsed = []
        for token in (raw or "").split(","):
            token = token.strip()
            if not token:
                continue
            parsed.append(_maybe_int(token))
        return parsed

    return {
        "api_id": os.getenv("TELEGRAM_API_ID"),
        "api_hash": os.getenv("TELEGRAM_API_HASH"),
        "shopee_app_id": os.getenv("SHOPEE_APP_ID"),
        "shopee_secret": os.getenv("SHOPEE_SECRET"),
        "channel_id": _maybe_int(os.getenv("TARGET_CHANNEL_ID")),
        "shopee_channel_id": _maybe_int(os.getenv("SHOPEE_CHANNEL_ID")),
        "ml_channel_id": _maybe_int(os.getenv("ML_CHANNEL_ID")),
        "source_chats": _chats(os.getenv("SOURCE_CHATS", "")),
        "dedup_db": os.getenv("DEDUP_DB", "dedup.db"),
        "hooks_file": os.getenv("HOOKS_FILE", "hooks.txt"),
        "amazon_tag": os.getenv("AMAZON_TAG"),
        "ml_matt_word": os.getenv("ML_MATT_WORD"),
        "ml_matt_tool": os.getenv("ML_MATT_TOOL"),
    }
