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
