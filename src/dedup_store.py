import sqlite3
import time
from pathlib import Path
from typing import Optional, Union


class DedupStore:
    """Recuerda qué productos ya se postearon, para no repetirlos.

    Un producto vuelve a estar disponible tras `ttl_days` (por si baja de
    precio de nuevo).
    """

    def __init__(self, db_path: Union[str, Path], ttl_days: int = 7):
        self._conn = sqlite3.connect(str(db_path))
        self._ttl_seconds = ttl_days * 86400
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS seen ("
            "item_id INTEGER PRIMARY KEY, ts REAL NOT NULL)"
        )
        self._conn.commit()

    def seen(self, item_id: int, *, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        row = self._conn.execute(
            "SELECT ts FROM seen WHERE item_id = ?", (item_id,)
        ).fetchone()
        if row is None:
            return False
        return (now - row[0]) < self._ttl_seconds

    def mark(self, item_id: int, *, now: Optional[float] = None) -> None:
        now = time.time() if now is None else now
        self._conn.execute(
            "INSERT OR REPLACE INTO seen (item_id, ts) VALUES (?, ?)",
            (item_id, now),
        )
        self._conn.commit()
