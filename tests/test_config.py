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
