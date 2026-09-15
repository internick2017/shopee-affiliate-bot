from decimal import Decimal

import src.config as config


def _no_op_load_dotenv(*args, **kwargs):
    """Stand-in for dotenv.load_dotenv that never reads a real .env file,
    so tests are isolated from whatever exists on disk."""
    return None


def test_numeric_channel_id_becomes_int(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", _no_op_load_dotenv)
    monkeypatch.setenv("TARGET_CHANNEL_ID", "-1001234567890")
    monkeypatch.delenv("SOURCE_CHATS", raising=False)

    cfg = config.load_config()

    assert cfg["channel_id"] == -1001234567890
    assert isinstance(cfg["channel_id"], int)


def test_source_chats_mixes_ints_and_strings(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", _no_op_load_dotenv)
    monkeypatch.setenv("SOURCE_CHATS", "-100123, Ofertas BR, 456")
    monkeypatch.delenv("TARGET_CHANNEL_ID", raising=False)

    cfg = config.load_config()

    assert cfg["source_chats"] == [-100123, "Ofertas BR", 456]


def test_non_numeric_channel_id_stays_string(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", _no_op_load_dotenv)
    monkeypatch.setenv("TARGET_CHANNEL_ID", "@meucanal")
    monkeypatch.delenv("SOURCE_CHATS", raising=False)

    cfg = config.load_config()

    assert cfg["channel_id"] == "@meucanal"


def test_shopee_channel_id_read_by_name(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", _no_op_load_dotenv)
    monkeypatch.setenv("SHOPEE_CHANNEL_ID", "Ofertas Shopee")
    monkeypatch.delenv("SOURCE_CHATS", raising=False)
    monkeypatch.delenv("TARGET_CHANNEL_ID", raising=False)

    cfg = config.load_config()

    assert cfg["shopee_channel_id"] == "Ofertas Shopee"


def test_shopee_channel_id_absent_is_none(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", _no_op_load_dotenv)
    monkeypatch.delenv("SHOPEE_CHANNEL_ID", raising=False)
    monkeypatch.delenv("SOURCE_CHATS", raising=False)

    cfg = config.load_config()

    assert cfg["shopee_channel_id"] is None


def test_ml_channel_id_read_by_name(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", _no_op_load_dotenv)
    monkeypatch.setenv("ML_CHANNEL_ID", "Ofertas ML")
    monkeypatch.delenv("SOURCE_CHATS", raising=False)
    monkeypatch.delenv("TARGET_CHANNEL_ID", raising=False)

    cfg = config.load_config()

    assert cfg["ml_channel_id"] == "Ofertas ML"


def test_ml_channel_id_absent_is_none(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", _no_op_load_dotenv)
    monkeypatch.delenv("ML_CHANNEL_ID", raising=False)
    monkeypatch.delenv("SOURCE_CHATS", raising=False)

    cfg = config.load_config()

    assert cfg["ml_channel_id"] is None


def test_ml_matt_word_and_tool_read_from_env(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", _no_op_load_dotenv)
    monkeypatch.setenv("ML_MATT_WORD", "lannybot")
    monkeypatch.setenv("ML_MATT_TOOL", "56889681")
    monkeypatch.delenv("SOURCE_CHATS", raising=False)
    monkeypatch.delenv("TARGET_CHANNEL_ID", raising=False)

    cfg = config.load_config()

    assert cfg["ml_matt_word"] == "lannybot"
    assert cfg["ml_matt_tool"] == "56889681"


def test_ml_matt_word_and_tool_absent_are_none(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", _no_op_load_dotenv)
    monkeypatch.delenv("ML_MATT_WORD", raising=False)
    monkeypatch.delenv("ML_MATT_TOOL", raising=False)
    monkeypatch.delenv("SOURCE_CHATS", raising=False)
    monkeypatch.delenv("TARGET_CHANNEL_ID", raising=False)

    cfg = config.load_config()

    assert cfg["ml_matt_word"] is None
    assert cfg["ml_matt_tool"] is None


def test_shopee_min_commission_pct_default(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", _no_op_load_dotenv)
    monkeypatch.delenv("SHOPEE_MIN_COMMISSION_PCT", raising=False)
    monkeypatch.delenv("SOURCE_CHATS", raising=False)
    monkeypatch.delenv("TARGET_CHANNEL_ID", raising=False)

    cfg = config.load_config()

    assert cfg["shopee_min_commission_pct"] == Decimal("6")


def test_shopee_min_commission_pct_custom_value(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", _no_op_load_dotenv)
    monkeypatch.setenv("SHOPEE_MIN_COMMISSION_PCT", "10")
    monkeypatch.delenv("SOURCE_CHATS", raising=False)
    monkeypatch.delenv("TARGET_CHANNEL_ID", raising=False)

    cfg = config.load_config()

    assert cfg["shopee_min_commission_pct"] == Decimal("10")


def test_shopee_min_commission_pct_malformed_falls_back_to_default(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", _no_op_load_dotenv)
    monkeypatch.setenv("SHOPEE_MIN_COMMISSION_PCT", "")
    monkeypatch.delenv("SOURCE_CHATS", raising=False)
    monkeypatch.delenv("TARGET_CHANNEL_ID", raising=False)

    cfg = config.load_config()

    assert cfg["shopee_min_commission_pct"] == Decimal("6")


def test_telegram_bot_token_read_from_env(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", _no_op_load_dotenv)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.delenv("SOURCE_CHATS", raising=False)
    monkeypatch.delenv("TARGET_CHANNEL_ID", raising=False)

    cfg = config.load_config()

    assert cfg["telegram_bot_token"] == "123:ABC"


def test_bot_allowed_users_parsed_as_int_set(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", _no_op_load_dotenv)
    monkeypatch.setenv("BOT_ALLOWED_USERS", "111, 222")
    monkeypatch.delenv("SOURCE_CHATS", raising=False)
    monkeypatch.delenv("TARGET_CHANNEL_ID", raising=False)

    cfg = config.load_config()

    assert cfg["bot_allowed_users"] == {111, 222}


def test_amazon_enabled_by_default(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", _no_op_load_dotenv)
    monkeypatch.delenv("AMAZON_ENABLED", raising=False)
    monkeypatch.delenv("SOURCE_CHATS", raising=False)
    monkeypatch.delenv("TARGET_CHANNEL_ID", raising=False)

    cfg = config.load_config()

    assert cfg["amazon_enabled"] is True


def test_amazon_enabled_empty_is_true(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", _no_op_load_dotenv)
    monkeypatch.setenv("AMAZON_ENABLED", "")
    monkeypatch.delenv("SOURCE_CHATS", raising=False)
    monkeypatch.delenv("TARGET_CHANNEL_ID", raising=False)

    cfg = config.load_config()

    assert cfg["amazon_enabled"] is True


def test_amazon_disabled_values(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", _no_op_load_dotenv)
    monkeypatch.delenv("SOURCE_CHATS", raising=False)
    monkeypatch.delenv("TARGET_CHANNEL_ID", raising=False)

    for raw in ("false", "False", " 0 ", "no", "OFF"):
        monkeypatch.setenv("AMAZON_ENABLED", raw)
        assert config.load_config()["amazon_enabled"] is False, raw


def test_bot_allowed_users_absent_is_empty_set(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", _no_op_load_dotenv)
    monkeypatch.delenv("BOT_ALLOWED_USERS", raising=False)
    monkeypatch.delenv("SOURCE_CHATS", raising=False)
    monkeypatch.delenv("TARGET_CHANNEL_ID", raising=False)

    cfg = config.load_config()

    assert cfg["bot_allowed_users"] == set()
