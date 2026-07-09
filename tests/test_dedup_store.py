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
    """La clave se normaliza a texto: un item_id int y su str son la misma entrada."""
    store = DedupStore(tmp_path / "d.db", ttl_days=7)
    store.mark(111, now=1000.0)
    assert store.seen("111", now=1000.0) is True


def test_claim_wins_once(tmp_path):
    store = DedupStore(tmp_path / "d.db", ttl_days=7)
    assert store.claim("amazon:B07QHKCG9N", now=1000.0) is True
    assert store.claim("amazon:B07QHKCG9N", now=1001.0) is False


def test_claim_is_atomic_so_a_concurrent_handler_cannot_also_win(tmp_path):
    """Consultar y después marcar dejaba una ventana: dos mensajes con la misma
    oferta la publicaban los dos. `claim` la cierra en una sola sentencia."""
    store = DedupStore(tmp_path / "d.db", ttl_days=7)
    winners = [store.claim("amazon:X", now=1000.0) for _ in range(5)]
    assert winners.count(True) == 1


def test_claim_again_after_ttl(tmp_path):
    store = DedupStore(tmp_path / "d.db", ttl_days=7)
    store.claim("amazon:X", now=1000.0)
    assert store.claim("amazon:X", now=1000.0 + 7 * 86400 + 1) is True


def test_release_lets_the_key_be_claimed_again(tmp_path):
    store = DedupStore(tmp_path / "d.db", ttl_days=7)
    store.claim("amazon:X", now=1000.0)
    store.release("amazon:X")
    assert store.claim("amazon:X", now=1001.0) is True


def test_purge_deletes_only_expired_keys(tmp_path):
    store = DedupStore(tmp_path / "d.db", ttl_days=7)
    store.mark("viejo", now=1000.0)
    store.mark("nuevo", now=1000.0 + 7 * 86400)
    later = 1000.0 + 7 * 86400 + 1

    assert store.purge(now=later) == 1
    assert store.seen("nuevo", now=later) is True
    assert store.seen("viejo", now=later) is False
