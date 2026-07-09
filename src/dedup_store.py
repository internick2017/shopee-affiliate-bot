import sqlite3
import time
from pathlib import Path
from typing import Optional, Union


class DedupStore:
    """Recuerda qué productos ya se postearon, para no repetirlos.

    La clave es texto (`"amazon:B07QHKCG9N"`, `"shopee:..."`), porque no toda
    plataforma identifica sus productos con un entero. Un `item_id` int se
    normaliza a str, así que el pipeline viejo de Shopee sigue andando.

    Un producto vuelve a estar disponible tras `ttl_days` (por si baja de
    precio de nuevo).
    """

    def __init__(self, db_path: Union[str, Path], ttl_days: int = 7):
        self._conn = sqlite3.connect(str(db_path))
        self._ttl_seconds = ttl_days * 86400
        # Tabla nueva (no `seen`): la vieja declaraba `item_id INTEGER PRIMARY KEY`,
        # que es un alias de rowid y rechaza texto. Un .db viejo conserva ese
        # esquema, así que se usa otro nombre en vez de intentar migrarlo.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS seen_keys ("
            "key TEXT PRIMARY KEY, ts REAL NOT NULL)"
        )
        self._conn.commit()

    def seen(self, key: Union[int, str], *, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        row = self._conn.execute(
            "SELECT ts FROM seen_keys WHERE key = ?", (str(key),)
        ).fetchone()
        if row is None:
            return False
        return (now - row[0]) < self._ttl_seconds

    def mark(self, key: Union[int, str], *, now: Optional[float] = None) -> None:
        now = time.time() if now is None else now
        self._conn.execute(
            "INSERT OR REPLACE INTO seen_keys (key, ts) VALUES (?, ?)",
            (str(key), now),
        )
        self._conn.commit()
