from src.dedup_store import DedupStore


def test_unseen_item_returns_false(tmp_path):
    store = DedupStore(tmp_path / "d.db", ttl_days=7)
    assert store.seen(111) is False


def test_marked_item_is_seen(tmp_path):
    store = DedupStore(tmp_path / "d.db", ttl_days=7)
    store.mark(111, now=1000.0)
    assert store.seen(111, now=1000.0) is True


def test_item_expires_after_ttl(tmp_path):
    store = DedupStore(tmp_path / "d.db", ttl_days=7)
    store.mark(111, now=1000.0)
    later = 1000.0 + 7 * 86400 + 1
    assert store.seen(111, now=later) is False


def test_persists_across_instances(tmp_path):
    db = tmp_path / "d.db"
    DedupStore(db).mark(111, now=1000.0)
    assert DedupStore(db).seen(111, now=1000.0) is True


def test_string_keys(tmp_path):
    """Las ofertas de Amazon se identifican por ASIN (texto), no por entero."""
    store = DedupStore(tmp_path / "d.db", ttl_days=7)
    assert store.seen("amazon:B07QHKCG9N") is False
    store.mark("amazon:B07QHKCG9N", now=1000.0)
    assert store.seen("amazon:B07QHKCG9N", now=1000.0) is True
    assert store.seen("amazon:B0754J12RW", now=1000.0) is False


def test_string_key_expires_after_ttl(tmp_path):
    store = DedupStore(tmp_path / "d.db", ttl_days=7)
    store.mark("amazon:B07QHKCG9N", now=1000.0)
    later = 1000.0 + 7 * 86400 + 1
    assert store.seen("amazon:B07QHKCG9N", now=later) is False


def test_int_and_str_key_are_the_same_entry(tmp_path):
    """run.py (pipeline viejo) marca con item_id int; debe seguir funcionando."""
    store = DedupStore(tmp_path / "d.db", ttl_days=7)
    store.mark(111, now=1000.0)
    assert store.seen("111", now=1000.0) is True
