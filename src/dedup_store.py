import sqlite3
import time
from pathlib import Path


class DedupStore:
    """Recuerda qué productos ya se postearon, para no repetirlos.

    La clave es texto (`"amazon:B07QHKCG9N"`, `"shopee:..."`), porque no toda
    plataforma identifica sus productos con un entero. Un `item_id` int se
    normaliza a str, así que el pipeline viejo de Shopee sigue andando.

    Un producto vuelve a estar disponible tras `ttl_days` (por si baja de
    precio de nuevo).

    Los handlers usan `claim`/`release`, no `seen`/`mark`: consultar y después
    marcar deja una ventana entre medio (el `await` del post) en la que otro
    mensaje concurrente ve la clave libre y publica la misma oferta dos veces.
    """

    def __init__(self, db_path: str | Path, ttl_days: int = 7):
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

    def claim(self, key: int | str, *, now: float | None = None) -> bool:
        """Reserva la clave. True si la ganó (hay que publicar), False si ya estaba.

        Es una sola sentencia, así que SQLite la resuelve atómicamente: no hay
        ventana entre el "¿está?" y el "marcala". Una clave vencida se re-reserva.
        """
        now = time.time() if now is None else now
        cursor = self._conn.execute(
            "INSERT INTO seen_keys (key, ts) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET ts = excluded.ts "
            "WHERE excluded.ts - seen_keys.ts >= ?",
            (str(key), now, self._ttl_seconds),
        )
        self._conn.commit()
        return cursor.rowcount == 1

    def release(self, key: int | str) -> None:
        """Suelta una clave reservada. Se usa cuando el post falló: la oferta no llegó
        a publicarse, así que debe reintentarse en el próximo mensaje."""
        self._conn.execute("DELETE FROM seen_keys WHERE key = ?", (str(key),))
        self._conn.commit()

    def purge(self, *, now: float | None = None) -> int:
        """Borra las claves vencidas y devuelve cuántas eran.

        El TTL solo se evaluaba al leer, así que la tabla crecía para siempre. El bot
        llama a esto al arrancar; no se hace en el constructor para no mezclar el reloj
        real con los tiempos inyectados de los tests.
        """
        now = time.time() if now is None else now
        cursor = self._conn.execute(
            "DELETE FROM seen_keys WHERE ? - ts >= ?", (now, self._ttl_seconds)
        )
        self._conn.commit()
        return cursor.rowcount

    def seen(self, key: int | str, *, now: float | None = None) -> bool:
        """Consulta sin reservar. Preferí `claim` antes de publicar."""
        now = time.time() if now is None else now
        row = self._conn.execute(
            "SELECT ts FROM seen_keys WHERE key = ?", (str(key),)
        ).fetchone()
        if row is None:
            return False
        return (now - row[0]) < self._ttl_seconds

    def mark(self, key: int | str, *, now: float | None = None) -> None:
        now = time.time() if now is None else now
        self._conn.execute(
            "INSERT OR REPLACE INTO seen_keys (key, ts) VALUES (?, ?)",
            (str(key), now),
        )
        self._conn.commit()
