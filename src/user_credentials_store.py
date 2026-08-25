import sqlite3
from pathlib import Path


class UserCredentialsStore:
    """Credenciales propias de Shopee Affiliate API por usuario del bot generador.

    Un usuario que registra sus propias `app_id`/`secret` (comando `/registrar_shopee`)
    recibe SU link de afiliado en el post, en vez del de la cuenta por defecto del
    `.env`. Sin registrar, el bot usa esas credenciales por defecto solo para leer los
    datos del producto (título/precio/foto), y devuelve el link tal cual lo mandó el
    usuario — ver `generate_post_reply` en `post_generator_bot.py`.
    """

    def __init__(self, db_path: str | Path):
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS user_credentials ("
            "user_id INTEGER PRIMARY KEY, app_id TEXT NOT NULL, secret TEXT NOT NULL)"
        )
        self._conn.commit()

    def save(self, user_id: int, app_id: str, secret: str) -> None:
        self._conn.execute(
            "INSERT INTO user_credentials (user_id, app_id, secret) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET app_id = excluded.app_id, secret = excluded.secret",
            (user_id, app_id, secret),
        )
        self._conn.commit()

    def get(self, user_id: int) -> tuple[str, str] | None:
        row = self._conn.execute(
            "SELECT app_id, secret FROM user_credentials WHERE user_id = ?", (user_id,)
        ).fetchone()
        return (row[0], row[1]) if row else None

    def remove(self, user_id: int) -> None:
        self._conn.execute("DELETE FROM user_credentials WHERE user_id = ?", (user_id,))
        self._conn.commit()
