"""Qué productos ya se usaron para grabar un video, para no repetirlos.

El porqué: con el plan actual de Flow salen unos 33 videos por mes. Repetir un
producto sin darse cuenta desperdicia el 3% de la produccion mensual, y encima el
canal publica dos veces lo mismo.

Se marca al pedir la referencia (`/video`), no al publicar: es el momento en que
el bot sabe que el producto fue elegido, y es el unico paso que pasa siempre por
el bot. Marcar al publicar exigiria que el usuario avise, y no lo va a hacer.

La clave es `item_id` de Shopee y no el link: `offerLink` es un shortlink de
tracking que puede cambiar entre llamadas para el mismo producto, asi que como
identidad no sirve.

A diferencia de `DedupStore` (que olvida a los `ttl_days` para poder re-postear una
oferta que bajo de precio), acá el olvido es OPCIONAL y explicito: un video ya
grabado sigue existiendo, no caduca. `olvidar()` esta para cuando se quiere volver
a grabar algo a proposito.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Grabado:
    item_id: int
    titulo: str
    ts: float

    @property
    def dias_atras(self) -> float:
        return (time.time() - self.ts) / 86400


class GrabadosStore:
    def __init__(self, db_path: str | Path):
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS grabados ("
            "item_id INTEGER PRIMARY KEY, ts REAL NOT NULL, titulo TEXT, user_id INTEGER)"
        )
        self._conn.commit()

    def marcar(
        self,
        item_id: int,
        *,
        titulo: str = "",
        user_id: int | None = None,
        now: float | None = None,
    ) -> None:
        """Registra que se pidio la referencia de este producto. Pedirla dos veces
        actualiza la fecha en vez de fallar: el usuario puede repetir el comando."""
        now = time.time() if now is None else now
        self._conn.execute(
            "INSERT INTO grabados (item_id, ts, titulo, user_id) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(item_id) DO UPDATE SET ts=excluded.ts, titulo=excluded.titulo",
            (int(item_id), now, titulo, user_id),
        )
        self._conn.commit()

    def ya_grabado(self, item_id: int) -> bool:
        fila = self._conn.execute(
            "SELECT 1 FROM grabados WHERE item_id = ?", (int(item_id),)
        ).fetchone()
        return fila is not None

    def grabados(self, item_ids: list[int]) -> set[int]:
        """Cuáles de esos ids ya se grabaron. En bloque para no hacer una consulta
        por producto al filtrar una lista de ideas."""
        if not item_ids:
            return set()
        marcas = ",".join("?" * len(item_ids))
        filas = self._conn.execute(
            f"SELECT item_id FROM grabados WHERE item_id IN ({marcas})",
            [int(i) for i in item_ids],
        ).fetchall()
        return {int(f[0]) for f in filas}

    def grabados_todos(self) -> set[int]:
        """Todos los ids grabados. Para filtrar listas de candidatos que vienen de
        la API, donde todavia no se sabe que ids van a aparecer."""
        return {int(f[0]) for f in self._conn.execute("SELECT item_id FROM grabados")}

    def olvidar(self, item_id: int) -> bool:
        """Permite volver a grabarlo. True si estaba registrado."""
        cur = self._conn.execute("DELETE FROM grabados WHERE item_id = ?", (int(item_id),))
        self._conn.commit()
        return cur.rowcount > 0

    def ultimos(self, cuantos: int = 10) -> list[Grabado]:
        filas = self._conn.execute(
            "SELECT item_id, titulo, ts FROM grabados ORDER BY ts DESC LIMIT ?",
            (max(1, cuantos),),
        ).fetchall()
        return [Grabado(item_id=f[0], titulo=f[1] or "", ts=f[2]) for f in filas]

    def total(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM grabados").fetchone()[0])
