"""Historial diario de ventas por producto, para detectar qué está despegando.

El porqué: `productOfferV2` devuelve `sales` como un número puntual, el acumulado
de siempre. Con eso sabés qué vendió mucho históricamente, que es casi siempre lo
más saturado: lo que ya publicó todo el mundo. Lo que no te dice es qué está
creciendo AHORA, que es cuándo conviene grabar.

Guardando ese número cada día, la diferencia entre dos días da la derivada: ventas
nuevas por día. Un producto que pasó de 800 a 3.000 en una semana está despegando;
uno con 70.000 estancado ya pasó su momento.

Una fila por producto y por día. La clave es (item_id, dia) para que correr el
muestreo dos veces el mismo día actualice en vez de duplicar.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

_DIA = 86400


@dataclass
class Tendencia:
    """Crecimiento de un producto entre dos muestras."""

    item_id: int
    titulo: str
    ventas_antes: int
    ventas_ahora: int
    dias: float
    precio: float
    comision_pct: float
    link: str

    @property
    def nuevas(self) -> int:
        return self.ventas_ahora - self.ventas_antes

    @property
    def por_dia(self) -> float:
        return self.nuevas / self.dias if self.dias > 0 else 0.0

    @property
    def crecimiento_pct(self) -> float:
        """Cuánto crecio sobre su propia base. Un producto chico que duplica es
        mas interesante que uno enorme que suma lo mismo en absoluto."""
        return (self.nuevas / self.ventas_antes * 100) if self.ventas_antes > 0 else 0.0


class TrendStore:
    def __init__(self, db_path: str | Path):
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS ventas_diarias ("
            "item_id INTEGER NOT NULL, dia INTEGER NOT NULL, ts REAL NOT NULL,"
            "ventas INTEGER NOT NULL, precio REAL, comision_pct REAL,"
            "titulo TEXT, link TEXT,"
            "PRIMARY KEY (item_id, dia))"
        )
        self._conn.commit()

    def registrar(
        self,
        item_id: int,
        ventas: int,
        *,
        titulo: str = "",
        precio: float = 0.0,
        comision_pct: float = 0.0,
        link: str = "",
        now: float | None = None,
    ) -> None:
        """Guarda la muestra de hoy. Correrlo dos veces el mismo día pisa la
        anterior en vez de duplicar: la clave incluye el día."""
        now = time.time() if now is None else now
        self._conn.execute(
            "INSERT INTO ventas_diarias (item_id, dia, ts, ventas, precio, comision_pct,"
            " titulo, link) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(item_id, dia) DO UPDATE SET ts=excluded.ts, ventas=excluded.ventas,"
            " precio=excluded.precio, comision_pct=excluded.comision_pct,"
            " titulo=excluded.titulo, link=excluded.link",
            (int(item_id), int(now // _DIA), now, int(ventas), float(precio),
             float(comision_pct), titulo, link),
        )
        self._conn.commit()

    def dias_con_datos(self) -> int:
        """Cuántos días distintos hay muestreados. Con menos de 2 no hay derivada
        que calcular, y conviene decirlo en vez de devolver una lista vacía."""
        fila = self._conn.execute("SELECT COUNT(DISTINCT dia) FROM ventas_diarias").fetchone()
        return int(fila[0]) if fila else 0

    def tendencias(
        self,
        *,
        ventana_dias: int = 7,
        minimo_nuevas: int = 30,
        excluir: set[int] | None = None,
        now: float | None = None,
    ) -> list[Tendencia]:
        """Productos que crecieron, ordenados por crecimiento relativo.

        Compara la muestra más reciente de cada producto contra la más vieja
        dentro de la ventana. `minimo_nuevas` filtra el ruido: sin eso, un
        producto que sumó 2 ventas desde una base de 3 aparece como +66%."""
        now = time.time() if now is None else now
        desde = int((now - ventana_dias * _DIA) // _DIA)
        filas = self._conn.execute(
            "SELECT item_id, titulo, link, "
            "  MIN(dia), MAX(dia), "
            "  (SELECT ventas FROM ventas_diarias v2 WHERE v2.item_id = v1.item_id"
            "     AND v2.dia >= ? ORDER BY v2.dia ASC LIMIT 1), "
            "  (SELECT ventas FROM ventas_diarias v3 WHERE v3.item_id = v1.item_id"
            "     ORDER BY v3.dia DESC LIMIT 1), "
            "  (SELECT precio FROM ventas_diarias v4 WHERE v4.item_id = v1.item_id"
            "     ORDER BY v4.dia DESC LIMIT 1), "
            "  (SELECT comision_pct FROM ventas_diarias v5 WHERE v5.item_id = v1.item_id"
            "     ORDER BY v5.dia DESC LIMIT 1) "
            "FROM ventas_diarias v1 WHERE dia >= ? GROUP BY item_id HAVING COUNT(*) >= 2",
            (desde, desde),
        ).fetchall()

        salida = []
        for item_id, titulo, link, dia_min, dia_max, antes, ahora, precio, com in filas:
            dias = max(1.0, float(dia_max - dia_min))
            t = Tendencia(
                item_id=item_id, titulo=titulo or "", ventas_antes=int(antes or 0),
                ventas_ahora=int(ahora or 0), dias=dias, precio=float(precio or 0),
                comision_pct=float(com or 0), link=link or "",
            )
            if t.nuevas >= minimo_nuevas and not (excluir and t.item_id in excluir):
                salida.append(t)
        salida.sort(key=lambda x: x.crecimiento_pct, reverse=True)
        return salida
