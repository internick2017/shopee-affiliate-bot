import os
from decimal import Decimal, InvalidOperation

from dotenv import load_dotenv

from .bot_access import parse_allowed_users


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


def _maybe_decimal(raw, default: str) -> Decimal:
    """Decimal(raw) si es un número válido; si no (ausente, vacío o malformado),
    Decimal(default)."""
    if raw:
        try:
            return Decimal(raw)
        except InvalidOperation:
            pass
    return Decimal(default)


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
        "trend_db": os.getenv("TREND_DB", "tendencias.db"),
        "grabados_db": os.getenv("GRABADOS_DB", "grabados.db"),
        "user_credentials_db": os.getenv("USER_CREDENTIALS_DB", "user_credentials.db"),
        "hooks_file": os.getenv("HOOKS_FILE", "hooks.txt"),
        "amazon_tag": os.getenv("AMAZON_TAG"),
        "ml_matt_word": os.getenv("ML_MATT_WORD"),
        "ml_matt_tool": os.getenv("ML_MATT_TOOL"),
        "shopee_min_commission_pct": _maybe_decimal(os.getenv("SHOPEE_MIN_COMMISSION_PCT"), "6"),
        "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
        "bot_allowed_users": parse_allowed_users(os.getenv("BOT_ALLOWED_USERS")),
    }
