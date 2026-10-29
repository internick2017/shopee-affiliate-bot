"""Cola diaria de posts para el grupo de WhatsApp de Lanny, enviada desde el celular.

Plan de Nick (2026-10-28, ver docs/analisis-grupo-whatsapp-2026-10-28.md):

  - 2 posts por hora, de 8:00 a 20:30 (el ultimo sale antes de las 21), de lunes a sabado. Domingo nada.
  - 80 % hogar, 20 % el rubro del dia (lunes masculino, martes belleza, miercoles
    electronicos, jueves ninos, viernes moda femenina, sabado una mezcla).
  - La cola se arma de cero cada manana con lo que Shopee tenga ese dia: precio,
    descuento y link salen del dia. Un producto puede volver, pero no en la misma
    semana (de lunes a sabado).

El post es solo texto con el link: WhatsApp arma solo la vista previa con la foto
(asi postea Lanny a mano). Por eso no se manda imagen.

El envio va por el celular de Nick (Galaxy A07, su numero publica en el grupo) con
uiautomator2, igual que el publicador de Shopee Video. Comparten el celular, asi
que comparten el candado `logs/publicador.lock`.
"""

from __future__ import annotations

import datetime as dt
import logging
import random
import re
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from .familias import familia as _familia
from .models import Product
from .post_builder import HookBank, build_post, rango_relevante
from .product_ideas import Idea, _normalizar
from .publicador_celular import bloqueado

log = logging.getLogger(__name__)

GRUPO = "#1 Nosso Grupo | Lanny"
PAQUETE = "com.whatsapp"

PRIMERA_HORA = 8
ULTIMA_HORA = 20            # el ultimo envio es 20:30 (20:45 con el azar): a las 21 ya no sale nada
PORCENTAJE_RUBRO = 0.2
# Mercado Livre sale de las ofertas que el bot ya monetiza con el link de Lanny, no de
# una busqueda: se elige al momento de mandar, porque una oferta de ML dura horas.
PORCENTAJE_ML = 0.1
ML_FRESCA_HORAS = 12
# Hogar en ML se reconoce por el titulo: esas ofertas no traen categoria.
HOGAR_ML = (
    "pote", "organizador", "toalha", "lencol", "jogo de cama", "edredom", "travesseiro",
    "panela", "frigideira", "cozinha", "banheiro", "tapete", "cortina", "limpeza", "mop",
    "vassoura", "lixeira", "prateleira", "cabide", "talher", "copo", "garrafa termica",
    "escorredor", "utensilio", "assadeira", "liquidificador", "air fryer", "airfryer",
    "cafeteira", "chaleira", "ventilador", "cesto", "varal", "sapateira", "luminaria",
    "colcha", "manta", "aspirador", "faca", "tabua", "marmita",
)
# Palabras que delatan un suplemento aunque el titulo diga "pote" o "potes".
NO_HOGAR_ML = ("propolis", "creatina", "whey", "colageno", "vitamina", "suplemento",
               "capsula", "omega 3", "mg por dose", "por dose")
# Productos de auto que el vendedor carga en Casa e Cozinha (2026-10-29: un conector
# de inflador de pneus salio como post de hogar). Palabras enteras y especificas:
# "carro" solo no sirve, la espuma de limpieza dice "Sofa, Estofado, Banco de Carro".
NO_CASA = ("pneu", "pneus", "automotivo", "automotiva", "automotivos", "veicular")
# Si el celular se toco hace menos que esto, alguien lo esta usando (a mano u otra
# automatizacion): no se le abre WhatsApp encima.
EN_USO_MS = 3 * 60 * 1000
# Lo vendido por WhatsApp en 89 dias fue de R$ 9,90 a R$ 109,99 (mediana R$ 29,90):
# una impresora o un tablet no es lo que este grupo compra.
PRECIO_MAXIMO = Decimal("120")
CASA_E_COZINHA = 100636
# Cada post sale entre :00 y :15 (o :30 y :45) de su media hora, al azar: el horario
# cambia todos los dias y entre dos posts nunca hay menos de 15 minutos.
CORRIMIENTO_MAXIMO = 15

# Busquedas de cada rubro. Las que son alias de product_ideas.CATEGORIAS buscan por
# categoria; el resto por palabra clave. Hogar tiene varias para que 22 productos
# por dia no salgan siempre del mismo pozo de 50.
HOGAR = (
    "casa", "organizador cozinha", "utensilios cozinha", "limpeza", "banheiro",
    "decoracao casa", "lavanderia", "potes", "cama mesa banho", "organizador",
)
# 0 = lunes, como datetime.weekday(). Domingo (6) no tiene cola.
RUBRO_DEL_DIA: dict[int, tuple[str, ...]] = {
    0: ("masculino", "camisa masculina", "relogios"),
    1: ("beleza", "maquiagem", "skincare"),
    2: ("celular", "audio", "informatica"),
    3: ("infantil", "brinquedos", "bebe"),
    4: ("moda", "vestido feminino", "bolsas"),
    5: ("masculino", "beleza", "audio", "infantil", "moda"),
}


@dataclass
class Envio:
    fecha: str          # "2026-10-28"
    hora: str           # "08:30"
    rubro: str          # "hogar", "ml" o la busqueda del rubro del dia
    item_id: int
    titulo: str
    texto: str
    estado: str = "pendiente"   # pendiente | enviando | enviado | vencido | fallido | sin_foto | repetido
    enviado_ts: float | None = None


# ---------------------------------------------------------------- parte pura


def horarios() -> list[str]:
    return [f"{h:02d}:{m:02d}" for h in range(PRIMERA_HORA, ULTIMA_HORA + 1) for m in (0, 30)]


def plan_del_dia(fecha: dt.date) -> list[tuple[str, str]]:
    """(hora, rubro) de cada envio del dia. Los del rubro del dia quedan repartidos
    a lo largo del dia, no amontonados al final."""
    rubros = RUBRO_DEL_DIA.get(fecha.weekday())
    if rubros is None:
        return []
    horas = horarios()
    n_rubro = round(len(horas) * PORCENTAJE_RUBRO)
    posiciones = {int((i + 0.5) * len(horas) / n_rubro) for i in range(n_rubro)}
    n_ml = round(len(horas) * PORCENTAJE_ML)
    # Si caen sobre uno del rubro del dia, pasan al horario siguiente.
    pos_ml = {p + (p in posiciones) for p in (int((i + 0.5) * len(horas) / n_ml) for i in range(n_ml))}
    plan, k = [], 0
    for i, hora in enumerate(horas):
        if i in posiciones:
            plan.append((hora, rubros[k % len(rubros)]))
            k += 1
        elif i in pos_ml:
            plan.append((hora, "ml"))
        else:
            plan.append((hora, "hogar"))
    return plan


def corrida(hora: str, azar: random.Random) -> str:
    """La hora base ("08:30") movida unos minutos al azar ("08:41")."""
    h, m = map(int, hora.split(":"))
    m += azar.randint(0, CORRIMIENTO_MAXIMO)
    return f"{h:02d}:{m:02d}"


def sirve(rubro: str, idea: Idea) -> bool:
    """Hogar tiene que ser de Casa e Cozinha: buscar "potes" tambien trae creatina."""
    if idea.precio > PRECIO_MAXIMO:
        return False
    if rubro not in ("hogar", "ml"):
        return True
    palabras = set(re.findall(r"[a-z0-9]+", _normalizar(idea.titulo)))
    return idea.categorias[:1] == (CASA_E_COZINHA,) and not palabras & set(NO_CASA)


def es_hogar_ml(titulo: str) -> bool:
    t = _normalizar(titulo)
    # "03 POTES do PROPOLIS 1000mg" es un suplemento, no un pote de cocina.
    if any(p in t for p in NO_HOGAR_ML):
        return False
    return any(p in t for p in HOGAR_ML)


def en_uso(dumpsys_power: str) -> bool:
    """Si alguien toco el celular hace poco, segun `dumpsys power`."""
    m = re.search(r"lastUserActivityTime=\d+ \((\d+) ms ago\)", dumpsys_power)
    return m is not None and int(m.group(1)) < EN_USO_MS


def texto_del_post(idea: Idea, hook: str) -> str:
    """El mismo template que Lanny usa a mano (post_builder.build_post)."""
    previo = None
    if idea.descuento_pct > 0:
        # Shopee da el precio final y el % de descuento: el "De" se deriva.
        previo = (idea.precio / (1 - Decimal(idea.descuento_pct) / 100)).quantize(Decimal("0.01"))
    producto = Product(
        item_id=idea.item_id,
        shop_id=0,
        name=idea.titulo,
        price_final=idea.precio,
        image_url=idea.imagen_url or "",
        price_original=previo,
        affiliate_link=idea.link,
        is_price_range=rango_relevante(idea.precio_min, idea.precio_max),
    )
    return build_post(producto, hook)


def armar_cola(
    fecha: dt.date,
    buscar: Callable[[str, set[int]], list[Idea]],
    hooks: HookBank,
    *,
    excluir: set[int],
    excluir_familias: frozenset[str] = frozenset(),
    azar: random.Random | None = None,
) -> list[Envio]:
    """La cola del dia. `buscar(busqueda, excluir)` devuelve ideas ordenadas de
    mejor a peor; aca se reparten entre los horarios sin repetir producto ni
    "tipo" de producto (la familia: dos organizadores de cajon seguidos aburren).
    `excluir_familias` son los tipos ya mandados esta semana.

    Un horario que se queda sin candidato se saltea: mejor un hueco que un repetido."""
    azar = azar or random.Random()
    plan = plan_del_dia(fecha)
    usados = set(excluir)
    firmas: set[str] = set(excluir_familias)
    pozos: dict[str, list[Idea]] = {}
    turno_hogar = fecha.toordinal()     # cada dia arranca por otra busqueda de hogar
    cola = []
    for hora, rubro in plan:
        # Un horario de ML lleva de respaldo un producto de hogar de Shopee, por si a
        # esa hora no hay oferta de ML fresca.
        de_hogar = rubro in ("hogar", "ml")
        busquedas = [HOGAR[(turno_hogar + j) % len(HOGAR)] for j in range(len(HOGAR))] \
            if de_hogar else [rubro]
        if de_hogar:
            turno_hogar += 1
        elegida = None
        for b in busquedas:
            if b not in pozos:
                pozos[b] = buscar(b, usados)
            for idea in pozos[b]:
                if (idea.item_id not in usados and _familia(idea.titulo) not in firmas
                        and sirve(rubro, idea)):
                    elegida = idea
                    break
            if elegida:
                break
        if elegida is None:
            log.warning("Sin producto para %s (%s): queda el hueco", hora, rubro)
            continue
        usados.add(elegida.item_id)
        firmas.add(_familia(elegida.titulo))
        cola.append(Envio(fecha.isoformat(), corrida(hora, azar), rubro, elegida.item_id,
                          elegida.titulo, texto_del_post(elegida, hooks.next())))
    return cola


def reemplazo(
    rubro: str,
    fecha: dt.date,
    buscar: Callable[[str, set[int]], list[Idea]],
    hooks: HookBank,
    *,
    excluir: set[int],
    excluir_familias: frozenset[str] = frozenset(),
) -> tuple[Idea, str] | None:
    """Otro producto del mismo rubro para un horario cuyo post no sirvio (sin foto
    en la vista previa). Mismo horario, asi el tope diario y los porcentajes no se
    mueven. Un horario de ML cae al hogar de Shopee, como su respaldo."""
    busquedas = list(HOGAR) if rubro in ("hogar", "ml") else [rubro]
    for b in busquedas:
        for idea in buscar(b, excluir):
            if (idea.item_id not in excluir and _familia(idea.titulo) not in excluir_familias
                    and sirve(rubro, idea)):
                return idea, texto_del_post(idea, hooks.next())
    return None


def a_enviar(cola: list[Envio], ahora: dt.datetime) -> tuple[Envio | None, list[Envio]]:
    """(el que toca mandar ahora, los que ya no vale la pena mandar).

    Toca el pendiente mas reciente cuya hora ya paso. Los pendientes anteriores a
    ese se dan por vencidos: si el celular estuvo ocupado una hora, recuperar todo
    junto seria una rafaga de posts en el grupo, justo lo que hace silenciarlo."""
    hoy = ahora.date().isoformat()
    vencidos = [e for e in cola if e.fecha == hoy and e.estado == "pendiente"
                and e.hora <= ahora.strftime("%H:%M")]
    if not vencidos:
        return None, []
    vencidos.sort(key=lambda e: e.hora)
    return vencidos[-1], vencidos[:-1]


# ------------------------------------------------------------------ registro


class ColaStore:
    """La cola y el registro de lo mandado, en una sola tabla: cada fila es un
    envio planeado y su estado. Es lo que permite medir en 30 dias que se mando."""

    def __init__(self, ruta: str | Path):
        # 30 s y no los 5 de sqlite: el bot de ofertas escribe en la misma base y el
        # 2026-10-29 un "database is locked" al marcar hizo mandar dos veces el mismo post.
        self._db = sqlite3.connect(str(ruta), timeout=30)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS envios (fecha TEXT, hora TEXT, rubro TEXT, "
            "item_id INTEGER, titulo TEXT, texto TEXT, estado TEXT, enviado_ts REAL, "
            "PRIMARY KEY (fecha, hora))"
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS ml_candidatos (item_id TEXT PRIMARY KEY, titulo TEXT, "
            "texto TEXT, ts REAL, enviado_ts REAL)"
        )
        self._db.commit()

    def guardar(self, cola: list[Envio]) -> None:
        self._db.executemany(
            "INSERT OR IGNORE INTO envios VALUES (?,?,?,?,?,?,?,?)",
            [(e.fecha, e.hora, e.rubro, e.item_id, e.titulo, e.texto, e.estado, e.enviado_ts)
             for e in cola],
        )
        self._db.commit()

    def del_dia(self, fecha: dt.date) -> list[Envio]:
        filas = self._db.execute(
            "SELECT * FROM envios WHERE fecha = ? ORDER BY hora", (fecha.isoformat(),))
        return [Envio(*f) for f in filas]

    def marcar(self, e: Envio, estado: str) -> None:
        ts = time.time() if estado == "enviado" else None
        self._db.execute("UPDATE envios SET estado = ?, enviado_ts = ? WHERE fecha = ? AND hora = ?",
                         (estado, ts, e.fecha, e.hora))
        self._db.commit()
        e.estado, e.enviado_ts = estado, ts

    def ultimo_envio(self, fecha: dt.date) -> float | None:
        """Cuando salio el ultimo post del dia (epoch), para no mandar dos seguidos."""
        fila = self._db.execute("SELECT MAX(enviado_ts) FROM envios WHERE fecha = ? AND estado = 'enviado'",
                                (fecha.isoformat(),)).fetchone()
        return fila[0] if fila else None

    def reemplazar(self, e: Envio, titulo: str, texto: str, item_id: int | None = None) -> None:
        item_id = e.item_id if item_id is None else item_id
        self._db.execute(
            "UPDATE envios SET titulo = ?, texto = ?, item_id = ? WHERE fecha = ? AND hora = ?",
            (titulo, texto, item_id, e.fecha, e.hora))
        self._db.commit()
        e.titulo, e.texto, e.item_id = titulo, texto, item_id

    def agregar_ml(self, texto: str, *, ahora: float | None = None) -> None:
        """Lo llama el bot de ofertas cada vez que publica una oferta de ML ya
        monetizada: el post queda como candidato para la cola."""
        titulo = next((ln.removeprefix("🛍️").strip() for ln in texto.splitlines()
                       if ln.startswith("🛍️")), "")
        m = re.search(r"MLB-?(\d+)", texto)
        clave = f"MLB{m.group(1)}" if m else _normalizar(titulo)
        if not clave:
            return
        self._db.execute(
            "INSERT INTO ml_candidatos VALUES (?,?,?,?,NULL) ON CONFLICT(item_id) "
            "DO UPDATE SET titulo = excluded.titulo, texto = excluded.texto, ts = excluded.ts",
            (clave, titulo, texto, time.time() if ahora is None else ahora),
        )
        self._db.commit()

    def candidato_ml(self, ahora: dt.datetime,
                     excluir_familias: frozenset[str] = frozenset()) -> tuple[str, str, str] | None:
        """(item_id, titulo, texto) de la oferta de ML de hogar mas reciente, fresca y
        no mandada esta semana; None si no hay."""
        lunes = dt.datetime.combine(ahora.date() - dt.timedelta(days=ahora.weekday()), dt.time())
        filas = self._db.execute(
            "SELECT item_id, titulo, texto FROM ml_candidatos WHERE ts >= ? "
            "AND (enviado_ts IS NULL OR enviado_ts < ?) ORDER BY ts DESC",
            (ahora.timestamp() - ML_FRESCA_HORAS * 3600, lunes.timestamp()),
        )
        return next((f for f in filas if es_hogar_ml(f[1])
                     and _familia(f[1]) not in excluir_familias), None)

    def marcar_ml_enviado(self, item_id: str) -> None:
        self._db.execute("UPDATE ml_candidatos SET enviado_ts = ? WHERE item_id = ?",
                         (time.time(), item_id))
        self._db.commit()

    def familias_de_la_semana(self, fecha: dt.date, *, salvo_hora: str | None = None) -> frozenset[str]:
        """Tipos de producto ya mandados desde el lunes de esa semana, mas los que
        quedan pendientes hoy (salvo el horario `salvo_hora`, que es el que se esta
        resolviendo): un tipo no se repite en la semana."""
        desde = (fecha - dt.timedelta(days=fecha.weekday())).isoformat()
        filas = self._db.execute(
            "SELECT titulo FROM envios WHERE fecha >= ? AND fecha <= ? AND "
            "(estado IN ('enviado', 'enviando') OR (fecha = ? AND estado = 'pendiente' AND hora != ?))",
            (desde, fecha.isoformat(), fecha.isoformat(), salvo_hora or ""))
        return frozenset(_familia(f[0]) for f in filas)

    def de_la_semana(self, fecha: dt.date) -> set[int]:
        """Productos planeados desde el lunes de esa semana (mandados o no): no se
        repiten hasta la semana que viene (decision de Nick, 2026-10-28)."""
        desde = (fecha - dt.timedelta(days=fecha.weekday())).isoformat()
        return {f[0] for f in self._db.execute(
            "SELECT item_id FROM envios WHERE fecha >= ? AND fecha < ?", (desde, fecha.isoformat()))}


# ------------------------------------------------------------ parte con pantalla


class EnvioAbortado(RuntimeError):
    """WhatsApp no mostro lo esperado. Se corta antes de mandar algo al chat equivocado."""


class CelularNoDisponible(EnvioAbortado):
    """Bloqueado o en uso: el post queda pendiente y se prueba en la proxima corrida."""


class SinFoto(EnvioAbortado):
    """El link no da foto para la vista previa: sin foto el post no vende, no se manda."""


class WhatsApp:
    def __init__(self, d: Any, pasos: Any):
        self.d = d
        self.pasos = pasos

    @classmethod
    def conectar(cls, pasos: Any, serial: str | None = None) -> WhatsApp:
        import uiautomator2 as u2  # import tardio: los tests no necesitan el celular

        return cls(u2.connect(serial), pasos)

    def abrir_grupo(self, link: str, grupo: str = GRUPO, *, revisar_uso: bool = True) -> None:
        """Entra por el link de invitacion: si el numero ya es del grupo, WhatsApp
        abre el chat directo (medido 2026-10-28). Buscar por nombre en la lista de
        chats seria tocar resultados parecidos."""
        self.d.screen_on()
        time.sleep(1)
        if bloqueado(self.d.shell("dumpsys window").output):
            raise CelularNoDisponible("El celular esta bloqueado")
        if revisar_uso and en_uso(self.d.shell("dumpsys power").output):
            raise CelularNoDisponible("Alguien esta usando el celular")
        self.d.shell(f'am start -a android.intent.action.VIEW -d "{link}" {PAQUETE}')
        titulo = self.d(resourceId=f"{PAQUETE}:id/conversation_contact_name")
        if not titulo.wait(timeout=20) or titulo.get_text() != grupo:
            self.pasos.foto(self.d, "no_es_el_grupo")
            raise EnvioAbortado(f"El chat abierto no es {grupo!r}")

    def _tarjeta_con_foto(self, espera: float = 20) -> bool:
        """Medido 2026-10-28: con foto, la tarjeta tiene `thumb` desde el principio y
        suma `thumb_cross_fade` cuando la imagen carga. Sin foto (Shopee no la da para
        ese link) carga el `title` enseguida y nunca tiene `thumb`."""
        cargada = self.d(resourceId=f"{PAQUETE}:id/thumb_cross_fade")
        titulo = self.d(resourceId=f"{PAQUETE}:id/link_preview_content").child(
            resourceId=f"{PAQUETE}:id/title")
        limite = time.time() + espera
        sin_thumb = 0   # segundos seguidos con titulo y sin thumb
        while time.time() < limite:
            if cargada.exists:
                time.sleep(1)  # que termine el fundido de la imagen
                return True
            if titulo.exists and not self.d(resourceId=f"{PAQUETE}:id/thumb").exists:
                sin_thumb += 1
                # 2026-10-28 12:44: un solo sondeo dio "sin foto" con la foto a la vista
                # (carrera con la animacion). Hace falta que se sostenga unos segundos.
                if sin_thumb >= 5:
                    break
            else:
                sin_thumb = 0
            time.sleep(1)
        # Volcado para ver que ids tenia la pantalla si vuelve a pasar.
        self.pasos.foto(self.d, "sin_foto_jerarquia")
        (Path(self.pasos.carpeta) / "jerarquia.xml").write_text(
            self.d.dump_hierarchy(), encoding="utf-8")
        return False

    def mandar(self, texto: str, *, enviar: bool) -> None:
        caja = self.d(resourceId=f"{PAQUETE}:id/entry")
        if not caja.wait(timeout=10):
            raise EnvioAbortado("No aparecio la caja de mensaje")
        caja.set_text(texto)
        if caja.get_text() != texto:
            caja.clear_text()
            raise EnvioAbortado("El texto no quedo entero en la caja")
        if not (self._tarjeta_con_foto() or self._tarjeta_con_foto(espera=10)):
            self.pasos.foto(self.d, "sin_foto")
            caja.clear_text()
            self.d.press("back")
            raise SinFoto("La vista previa del link no trae foto")
        self.pasos.foto(self.d, "listo_para_enviar")
        if not enviar:
            caja.clear_text()
            self.d.press("back")
            return
        self.d(resourceId=f"{PAQUETE}:id/send").click()
        time.sleep(3)
        self.pasos.foto(self.d, "despues_de_enviar")
        if caja.get_text() == texto:
            raise EnvioAbortado("Despues de Enviar el texto sigue en la caja")
        self.d.press("back")

    def _descartar_foto(self) -> None:
        """Salir del editor sin mandar: WhatsApp pregunta "Deseja descartar a foto?"."""
        self.d.press("back")
        descartar = self.d(text="Descartar")
        if descartar.wait(timeout=5):
            descartar.click()
        self.d.press("back")  # de la lista de chats para compartir

    def mandar_con_foto(self, texto: str, foto: Path, grupo: str = GRUPO, *, enviar: bool) -> None:
        """Si la vista previa del link no trae foto, la foto del producto va como imagen
        y el post como leyenda (2026-10-29: se perdian horarios enteros por esto). Se
        comparte al grupo con el intent SEND, eligiendo el grupo por su nombre exacto."""
        destino = f"/sdcard/Download/cola/{foto.name}"
        self.d.push(str(foto), destino)
        self.d.shell(f"am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file://{destino}")
        self.d.shell(f"am start -a android.intent.action.SEND -t image/jpeg "
                     f"--eu android.intent.extra.STREAM file://{destino} -p {PAQUETE}")
        fila = self.d(text=grupo, resourceId=f"{PAQUETE}:id/contactpicker_row_name")
        lupa = self.d(resourceId=f"{PAQUETE}:id/menuitem_search")
        # El grupo no siempre esta entre los frecuentes (2026-10-29 13:12): se busca por nombre.
        if not fila.wait(timeout=5) and lupa.wait(timeout=10):
            lupa.click()
            self.d(className="android.widget.EditText").set_text(grupo)
            time.sleep(2)
        if not fila.wait(timeout=10):
            self.pasos.foto(self.d, "sin_grupo_para_compartir")
            self.d.press("back")
            raise EnvioAbortado(f"No aparecio {grupo!r} para compartir la foto")
        fila.click()
        miniatura = self.d(resourceId=f"{PAQUETE}:id/thumbnail")  # abre el editor (medido 2026-10-29)
        if not miniatura.wait(timeout=10):
            self.pasos.foto(self.d, "sin_miniatura")
            self.d.press("back")
            raise EnvioAbortado("No aparecio la miniatura de la foto")
        miniatura.click()
        leyenda = self.d(resourceId=f"{PAQUETE}:id/caption")
        if not leyenda.wait(timeout=15):
            self.pasos.foto(self.d, "sin_editor")
            raise EnvioAbortado("No se abrio el editor de la foto")
        leyenda.click()
        leyenda.set_text(texto)
        time.sleep(1)
        if self.d(description="Barra de espaço").exists:  # el teclado tapa el boton de enviar
            self.d.press("back")
        # WhatsApp puede normalizar espacios del final: alcanza con que este entero el cuerpo.
        if (leyenda.get_text() or "").strip() != texto.strip():
            self.pasos.foto(self.d, "leyenda_incompleta")
            self._descartar_foto()
            raise EnvioAbortado("La leyenda no quedo entera")
        if not self.d(text=grupo).exists:
            self.pasos.foto(self.d, "otro_destinatario")
            self._descartar_foto()
            raise EnvioAbortado(f"El destinatario no es {grupo!r}")
        self.pasos.foto(self.d, "foto_lista_para_enviar")
        if not enviar:
            self._descartar_foto()
            return
        self.d(resourceId=f"{PAQUETE}:id/send").click()
        time.sleep(4)
        self.pasos.foto(self.d, "foto_enviada")
        # 2026-10-29 17:15: la foto salio sin leyenda aunque la captura previa la mostraba.
        # Si el link no aparece en el chat, el post va como texto debajo de la foto.
        if self.falta_leyenda(texto):
            self.pasos.foto(self.d, "foto_sin_leyenda")
            self.texto_suelto(texto)
        self.d.press("back")

    def falta_leyenda(self, texto: str) -> bool:
        """True si el link del post no aparece en el chat despues de mandar la foto."""
        link = re.search(r"https?://\S+", texto)
        return bool(link) and not self.d(textContains=link.group(0)).wait(timeout=10)

    def texto_suelto(self, texto: str) -> None:
        """Manda el texto tal cual en el chat abierto, sin mirar la vista previa."""
        caja = self.d(resourceId=f"{PAQUETE}:id/entry")
        if not caja.wait(timeout=10):
            raise EnvioAbortado("No aparecio la caja de mensaje para el texto")
        caja.set_text(texto)
        if caja.get_text() != texto:
            caja.clear_text()
            raise EnvioAbortado("El texto no quedo entero en la caja")
        self.d(resourceId=f"{PAQUETE}:id/send").click()
        time.sleep(3)
        self.pasos.foto(self.d, "texto_suelto_enviado")
