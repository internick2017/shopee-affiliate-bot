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
import statistics
import time
from collections.abc import Iterable
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


@dataclass(frozen=True)
class Muestra:
    """Lo que se anota de un producto en un dia."""

    item_id: int
    ventas: int
    titulo: str = ""
    precio: float = 0.0
    comision_pct: float = 0.0
    link: str = ""


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
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS alertas_precio ("
            "item_id INTEGER NOT NULL, dia INTEGER NOT NULL, PRIMARY KEY (item_id, dia))"
        )
        self._conn.commit()

    def registrar_muestras(self, muestras: Iterable[Muestra], *, now: float | None = None) -> None:
        """Guarda la tanda de hoy en una sola escritura a disco: entra entera o no
        entra. Cada escritura espera a que el disco confirme, y de a una fila el
        muestreo completo tardaba 8 minutos. Correrlo dos veces el mismo dia pisa
        la muestra anterior en vez de duplicar: la clave incluye el dia."""
        now = time.time() if now is None else now
        dia = int(now // _DIA)
        with self._conn:
            self._conn.executemany(
                "INSERT INTO ventas_diarias (item_id, dia, ts, ventas, precio, comision_pct,"
                " titulo, link) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(item_id, dia) DO UPDATE SET ts=excluded.ts, ventas=excluded.ventas,"
                " precio=excluded.precio, comision_pct=excluded.comision_pct,"
                " titulo=excluded.titulo, link=excluded.link",
                [(m.item_id, dia, now, m.ventas, m.precio, m.comision_pct, m.titulo, m.link)
                 for m in muestras],
            )

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
        """Una sola muestra: `registrar_muestras` con una tanda de uno."""
        self.registrar_muestras(
            [Muestra(int(item_id), int(ventas), titulo, float(precio), float(comision_pct), link)],
            now=now,
        )

    def precios_de_referencia(
        self,
        *,
        ventana_dias: int = 14,
        minimo_muestras: int = 3,
        now: float | None = None,
    ) -> dict[int, float]:
        """El precio normal de cada producto: la mediana de sus dias previos a hoy
        dentro de la ventana. La mediana aguanta una oferta puntual que un promedio
        arrastraria. Con menos de `minimo_muestras` dias no hay precio normal."""
        now = time.time() if now is None else now
        hoy = int(now // _DIA)
        precios: dict[int, list[float]] = {}
        for item_id, precio in self._conn.execute(
            "SELECT item_id, precio FROM ventas_diarias "
            "WHERE dia >= ? AND dia < ? AND precio > 0",
            (hoy - ventana_dias, hoy),
        ):
            precios.setdefault(int(item_id), []).append(float(precio))
        return {
            item_id: statistics.median(ps)
            for item_id, ps in precios.items()
            if len(ps) >= minimo_muestras
        }

    def ya_alertado(self, item_id: int, *, now: float | None = None) -> bool:
        """Si hoy ya se aviso de este producto."""
        now = time.time() if now is None else now
        return self._conn.execute(
            "SELECT 1 FROM alertas_precio WHERE item_id = ? AND dia = ?",
            (int(item_id), int(now // _DIA)),
        ).fetchone() is not None

    def marcar_alertado(self, item_id: int, *, now: float | None = None) -> bool:
        """Anota que hoy se aviso de este producto. False si ya estaba anotado: el
        muestreo puede correr varias veces al dia y el aviso va una sola."""
        now = time.time() if now is None else now
        cur = self._conn.execute(
            "INSERT OR IGNORE INTO alertas_precio (item_id, dia) VALUES (?, ?)",
            (int(item_id), int(now // _DIA)),
        )
        self._conn.commit()
        return cur.rowcount > 0

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
