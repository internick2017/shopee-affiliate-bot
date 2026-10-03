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


# Tope del campo "Adicionar legenda" de Shopee Video, hashtags incluidos.
MAX_LEGENDA = 150


def _validar_legenda(legenda: str) -> None:
    if len(legenda) > MAX_LEGENDA:
        raise ValueError(
            f"La legenda tiene {len(legenda)} caracteres; Shopee acepta hasta {MAX_LEGENDA}.")


@dataclass
class VideoProducido:
    item_id: int
    canal: str
    titulo: str
    link: str
    precio: float | None
    comision_pct: float | None
    herramienta: str
    marca: str
    archivo: str
    ts: float
    publicado_ts: float | None = None
    legenda: str | None = None

    @property
    def publicado(self) -> bool:
        return self.publicado_ts is not None

    @property
    def dias_publicado(self) -> float | None:
        """Cuanto lleva expuesto. Un "no vendio" a las horas de publicar no dice
        lo mismo que uno despues de dos semanas."""
        if self.publicado_ts is None:
            return None
        return (time.time() - self.publicado_ts) / 86400

    @property
    def comision_reais(self) -> float | None:
        """Lo que deja una venta. Es el numero con el que se elige que grabar:
        un 20% sobre R$10 no paga el tiempo de produccion."""
        if self.precio is None or self.comision_pct is None:
            return None
        return self.precio * self.comision_pct / 100


class VideosStore:
    """Los videos ya producidos, con el detalle para cruzarlos contra las ventas.

    Vive en la misma base que `GrabadosStore` pero en su propia tabla, y por dos
    motivos no reemplaza a aquella:

      - `grabados` tiene `item_id` como clave unica, sin canal. Nick y Lanny son
        cuentas de afiliado distintas con audiencias distintas: un producto grabado
        para una puede y debe poder grabarse para la otra. Aca la identidad es el
        par (item_id, canal).
      - `bot_generador` filtra sus ideas con `grabados_todos()`. Si los videos del
        canal de Nick entraran ahi, le sacarian productos a Lanny sin motivo.

    Por eso el flujo es: todo video se registra aca, y ademas se marca en `grabados`
    solo cuando el canal es el que consume el bot.

    El `item_id` es la clave para cruzar con `sales_report`: el `conversionReport`
    de Shopee lo trae por conversion, asi que con esta tabla se puede responder
    "de los productos a los que les hice video, cuales vendieron".
    """

    def __init__(self, db_path: str | Path):
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS videos_producidos ("
            "item_id INTEGER NOT NULL, canal TEXT NOT NULL, ts REAL NOT NULL, "
            "titulo TEXT, link TEXT, precio REAL, comision_pct REAL, "
            "herramienta TEXT, marca TEXT, archivo TEXT, publicado_ts REAL, "
            "legenda TEXT, PRIMARY KEY (item_id, canal))"
        )
        # Migracion para las bases creadas antes de que existieran estas columnas:
        # sin esto, una base ya poblada seguiria sin ellas y todo lo que la lea
        # fallaria.
        columnas = {f[1] for f in self._conn.execute(
            "PRAGMA table_info(videos_producidos)")}
        if "publicado_ts" not in columnas:
            self._conn.execute(
                "ALTER TABLE videos_producidos ADD COLUMN publicado_ts REAL")
        if "legenda" not in columnas:
            self._conn.execute(
                "ALTER TABLE videos_producidos ADD COLUMN legenda TEXT")
        self._conn.commit()

    def registrar(
        self,
        item_id: int,
        *,
        canal: str,
        titulo: str = "",
        link: str = "",
        precio: float | None = None,
        comision_pct: float | None = None,
        herramienta: str = "",
        marca: str = "",
        archivo: str = "",
        legenda: str | None = None,
        now: float | None = None,
    ) -> None:
        """Rehacer un video del mismo producto y canal pisa el registro anterior:
        lo que importa es el ultimo video entregado, no cada intento."""
        now = time.time() if now is None else now
        if legenda is not None:
            _validar_legenda(legenda)
        self._conn.execute(
            "INSERT INTO videos_producidos "
            "(item_id, canal, ts, titulo, link, precio, comision_pct, herramienta, marca, "
            "archivo, legenda) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(item_id, canal) DO UPDATE SET "
            "ts=excluded.ts, titulo=excluded.titulo, link=excluded.link, "
            "precio=excluded.precio, comision_pct=excluded.comision_pct, "
            # `publicado_ts` queda afuera a proposito: regenerar un link o
            # rehacer el video no cambia cuando se publico.
            "herramienta=excluded.herramienta, marca=excluded.marca, archivo=excluded.archivo, "
            # Sin legenda nueva se conserva la que habia: regenerar un link no
            # tiene por que perder el texto.
            "legenda=COALESCE(excluded.legenda, videos_producidos.legenda)",
            (int(item_id), canal, now, titulo, link, precio, comision_pct,
             herramienta, marca, archivo, legenda),
        )
        self._conn.commit()

    def poner_legenda(self, item_id: int, canal: str, legenda: str) -> bool:
        """Guarda el texto que se pega en Shopee Video al publicar (descripcion y
        hashtags). False si ese (item_id, canal) no existe."""
        _validar_legenda(legenda)
        cur = self._conn.execute(
            "UPDATE videos_producidos SET legenda = ? WHERE item_id = ? AND canal = ?",
            (legenda, int(item_id), canal),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def marcar_publicado(
        self, item_id: int, canal: str, *, cuando: float | None = None
    ) -> bool:
        """Registra que el video salio al aire. Se marca aparte de `registrar`
        porque publicar lo hace Nick a mano en Shopee Video, despues y por fuera de
        la produccion del video. False si ese (item_id, canal) no existe."""
        cur = self._conn.execute(
            "UPDATE videos_producidos SET publicado_ts = ? "
            "WHERE item_id = ? AND canal = ?",
            (time.time() if cuando is None else cuando, int(item_id), canal),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def marcar_si_falta(self, item_id: int, canal: str, *, cuando: float) -> bool:
        """Como `marcar_publicado`, pero sin pisar una fecha ya puesta: lo usa la
        sincronizacion para traer las marcas del panel, y la fecha mas vieja es la
        real. True si lo marco."""
        cur = self._conn.execute(
            "UPDATE videos_producidos SET publicado_ts = ? "
            "WHERE item_id = ? AND canal = ? AND publicado_ts IS NULL",
            (cuando, int(item_id), canal),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def sin_publicar(self, canal: str | None = None) -> list[VideoProducido]:
        """Videos producidos que todavia no salieron. Son plata parada: el costo
        ya se pago."""
        return [v for v in self.listar(canal=canal, cuantos=500) if not v.publicado]

    def ya_tiene_video(self, item_id: int, canal: str) -> bool:
        fila = self._conn.execute(
            "SELECT 1 FROM videos_producidos WHERE item_id = ? AND canal = ?",
            (int(item_id), canal),
        ).fetchone()
        return fila is not None

    def ids_del_canal(self, canal: str) -> set[int]:
        """Para filtrar una lista de candidatos antes de elegir que grabar."""
        return {
            int(f[0])
            for f in self._conn.execute(
                "SELECT item_id FROM videos_producidos WHERE canal = ?", (canal,)
            )
        }

    def listar(self, canal: str | None = None, cuantos: int = 50) -> list[VideoProducido]:
        sql = (
            "SELECT item_id, canal, titulo, link, precio, comision_pct, herramienta, "
            "marca, archivo, ts, publicado_ts, legenda FROM videos_producidos"
        )
        args: list = []
        if canal:
            sql += " WHERE canal = ?"
            args.append(canal)
        sql += " ORDER BY ts DESC LIMIT ?"
        args.append(max(1, cuantos))
        return [
            VideoProducido(
                item_id=f[0], canal=f[1], titulo=f[2] or "", link=f[3] or "",
                precio=f[4], comision_pct=f[5], herramienta=f[6] or "",
                marca=f[7] or "", archivo=f[8] or "", ts=f[9], publicado_ts=f[10],
                legenda=f[11],
            )
            for f in self._conn.execute(sql, args).fetchall()
        ]

    def olvidar(self, item_id: int, canal: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM videos_producidos WHERE item_id = ? AND canal = ?",
            (int(item_id), canal),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def total(self, canal: str | None = None) -> int:
        if canal:
            fila = self._conn.execute(
                "SELECT COUNT(*) FROM videos_producidos WHERE canal = ?", (canal,)
            ).fetchone()
        else:
            fila = self._conn.execute("SELECT COUNT(*) FROM videos_producidos").fetchone()
        return int(fila[0])
