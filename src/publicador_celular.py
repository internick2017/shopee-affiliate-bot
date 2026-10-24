"""Publicar en Shopee Video manejando el celular de Nick desde la PC.

Shopee Video no tiene API ni panel web: solo se publica desde la app. La ruta es
ADB al celular real (Galaxy A07, por cable o Wi-Fi) y `uiautomator2` para tocar
la app como lo haria una persona. Camino medido el 2026-10-15 (idea de Nick):

  abrir el link de afiliado del video en la app -> titulo (pagina completa) ->
  icono compartir -> "Comissao de Afiliados" -> "Compartilhe para Ganhar" ->
  "Shopee Video" -> pestana "Video" -> Biblioteca (el video recien copiado queda
  primero) -> "Proximo (1)" -> "Proximo" -> "Adicionar legenda": el producto YA
  viene vinculado; se escribe la legenda, se prende el rotulo de IA -> "Postar".

Entrar por el link y no por el buscador de "Adicionar produto" es a proposito: el
buscador falla seguido con "Sem resultado" y devuelve productos parecidos. Por el
link el producto es exactamente el del registro, y antes de postar igual se
verifica que el titulo vinculado coincida.

Los botones con texto se buscan por su texto, porque cambian de lugar. Solo los
iconos sin texto (compartir, la primera celda de la galeria) van por coordenada.

La parte que decide (que video sigue, si el producto coincide) es pura y tiene
tests. La que toca la pantalla vive en `Celular` y se prueba en vivo.
"""

from __future__ import annotations

import logging
import random
import re
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .grabados_store import VideoProducido, VideosStore

log = logging.getLogger(__name__)

PAQUETE = "com.shopee.br"
CARPETA_CELULAR = "/sdcard/DCIM/ShopeeBot"
CARPETA_VIDEOS = Path(__file__).resolve().parent.parent / "videos_entregados" / "shopee-video-flow"
# Decision de Nick (2026-10-15): 4 o 5 por dia. Mas que eso empieza a parecer robot.
TOPE_DIARIO = 5


class PublicacionAbortada(RuntimeError):
    """La app no mostro lo esperado. Se corta antes de publicar algo a medias."""


# ---------------------------------------------------------------- parte pura


def normalizar(texto: str) -> str:
    """Minusculas, sin acentos y sin signos, para comparar titulos de Shopee."""
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    limpio = "".join(c if c.isalnum() else " " for c in sin_acentos.lower())
    return " ".join(limpio.split())


def elegir_producto(titulo: str, candidatos: list[str]) -> int | None:
    """Indice del texto de pantalla que es el producto registrado, o None.

    Coincide si un titulo empieza con el otro (normalizados): el registro puede
    estar cortado y la app a veces corta el suyo. Exigir el prefijo entero, y no
    "se parece", es lo que separa el candado PRETO del candado Cinza."""
    buscado = normalizar(titulo)
    if not buscado:
        return None
    for i, cand in enumerate(candidatos):
        c = normalizar(cand)
        # Un texto corto ("Cadeado") empezaria cualquier titulo: no cuenta.
        if len(c) >= 20 and (c.startswith(buscado) or buscado.startswith(c)):
            return i
    return None


def es_verde(r: int, g: int, b: int) -> bool:
    """El verde de los interruptores prendidos de Shopee (~ (0, 175, 80)); el
    apagado es gris claro, con los tres canales parecidos."""
    return g > 120 and g > r + 60 and g > b + 30


def bloqueado(dumpsys_window: str) -> bool:
    """Si la pantalla de bloqueo esta arriba, segun `dumpsys window`. Con el PIN
    puesto no hay nada que hacer: el script no conoce ni debe conocer el PIN."""
    return "isKeyguardShowing=true" in dumpsys_window


def publicados_hoy(store: VideosStore, canal: str, *, ahora: float | None = None) -> int:
    """Cuantos videos del canal salieron desde la medianoche local, a mano o por la
    tarea. Es lo que hace cumplir el tope diario aunque se mezclen las dos vias."""
    ahora = time.time() if ahora is None else ahora
    medianoche = time.mktime(time.localtime(ahora)[:3] + (0, 0, 0, 0, 0, -1))
    return sum(1 for v in store.listar(canal, 100_000)
               if v.publicado_ts is not None and v.publicado_ts >= medianoche)


def ruta_video(archivo: str, carpeta: Path = CARPETA_VIDEOS) -> Path:
    """El registro guarda a veces la ruta entera y a veces solo el nombre."""
    p = Path(archivo)
    return p if p.is_absolute() else carpeta / p


def siguiente_video(
    store: VideosStore, canal: str, carpeta: Path = CARPETA_VIDEOS
) -> VideoProducido | None:
    """El video sin publicar mas reciente que esta listo: con legenda, titulo,
    link, el archivo en disco y la fidelidad aprobada. Los incompletos se saltean con un aviso en el log,
    asi una ficha a medio hacer no frena la cola."""
    for v in store.sin_publicar(canal):
        if not v.legenda or not v.titulo or not v.link:
            log.warning("Salteo %s: le falta legenda, titulo o link", v.item_id)
            continue
        if not v.fidelidad_ts:
            log.warning("Salteo %s: nadie confirmo que el video es fiel al producto "
                        "(python scripts/video/revisar_fidelidad.py)", v.item_id)
            continue
        if not ruta_video(v.archivo, carpeta).is_file():
            log.warning("Salteo %s: no existe el archivo %s", v.item_id, v.archivo)
            continue
        return v
    return None


# ------------------------------------------------------------ parte con pantalla


@dataclass
class Pasos:
    """Una captura por paso: si algo falla a las 3 de la mañana, es la unica
    forma de saber en que pantalla quedo la app."""

    carpeta: Path

    def __post_init__(self) -> None:
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self._n = 0

    def foto(self, d: Any, nombre: str) -> None:
        self._n += 1
        try:
            d.screenshot(str(self.carpeta / f"{self._n:02d}_{nombre}.png"))
        except Exception:  # una captura fallida no tiene que tumbar la publicacion
            log.exception("No pude sacar la captura %s", nombre)


def _pausa(minimo: float = 1.5, maximo: float = 3.5) -> None:
    """Ritmo de persona entre toques. La cuenta de Lanny ya fue restringida una
    vez: no hay que darle a Shopee motivos para ver un robot."""
    time.sleep(random.uniform(minimo, maximo))


class Celular:
    def __init__(self, d: Any, pasos: Pasos):
        self.d = d
        self.pasos = pasos

    @classmethod
    def conectar(cls, pasos: Pasos, serial: str | None = None) -> Celular:
        import uiautomator2 as u2  # import tardio: los tests no necesitan el celular

        return cls(u2.connect(serial), pasos)

    def _tocar(self, texto: str, *, espera: float = 15, contiene: bool = False) -> None:
        sel = self.d(textContains=texto) if contiene else self.d(text=texto)
        if not sel.wait(timeout=espera):
            self.pasos.foto(self.d, "falta_" + normalizar(texto).replace(" ", "_")[:30])
            raise PublicacionAbortada(f"No aparecio {texto!r}")
        sel.click()
        _pausa()

    def textos(self) -> list[str]:
        return re.findall(r'text="([^"]+)"', self.d.dump_hierarchy())

    def verificar_desbloqueado(self) -> None:
        self.d.screen_on()
        time.sleep(1)
        if bloqueado(self.d.shell("dumpsys window").output):
            raise PublicacionAbortada(
                "El celular esta bloqueado. Dejalo enchufado con 'Permanecer ativo' prendido "
                "en Opcoes do desenvolvedor, asi la pantalla no se apaga ni se bloquea.")

    def copiar_video(self, local: Path) -> None:
        destino = f"{CARPETA_CELULAR}/{local.name}"
        self.d.shell(f"mkdir -p {CARPETA_CELULAR}")
        self.d.push(str(local), destino)
        # Sin el aviso al media scanner la galeria no lo muestra hasta reiniciar.
        self.d.shell(f"am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file://{destino}")
        time.sleep(3)

    def abrir_producto(self, link: str, titulo: str, *, pagina_directa: bool = False) -> None:
        self.d.screen_on()
        self.d.app_stop(PAQUETE)
        self.d.shell(f'am start -a android.intent.action.VIEW -d "{link}" {PAQUETE}')
        # El link abre una vista corta; tocando el titulo se pasa a la pagina
        # completa, que es la que tiene el icono de compartir. Algunos links abren
        # directo en la pagina completa: ahi no hay titulo corto que tocar.
        if pagina_directa:
            time.sleep(5)
        else:
            primeras = " ".join(titulo.split()[:4])
            self._tocar(primeras, espera=30, contiene=True)
        if not self.d(textContains="Quantidade").wait(timeout=20):
            log.info("No vi 'Quantidade': sigo, la pagina puede variar por producto")
        self.pasos.foto(self.d, "pagina_producto")

    def ir_a_shopee_video(self) -> None:
        self.d.click(510, 117)  # icono compartir de la barra superior, sin texto
        _pausa()
        self._tocar("Comissão de Afiliados", contiene=True)
        self._tocar("Compartilhe para Ganhar")
        self._tocar("Shopee Video")
        # Abre en "Modelos"; el video propio se sube desde la pestana "Vídeo".
        self._tocar("Vídeo", espera=20)
        self._tocar("Biblioteca")
        self.pasos.foto(self.d, "galeria")

    def elegir_primer_video(self) -> None:
        # La primera celda de la grilla es lo ultimo que entro a la galeria, o sea
        # el video recien copiado. Su circulo de seleccion no tiene texto, pero la
        # celda de arriba a la izquierda no se mueve.
        self.d.click(150, 281)
        _pausa()
        self._tocar("Próximo (1)")
        self._tocar("Próximo", espera=30)
        if not self.d(text="Adicionar legenda").wait(timeout=30):
            self.pasos.foto(self.d, "sin_pantalla_legenda")
            raise PublicacionAbortada("No llego a la pantalla 'Adicionar legenda'")

    def verificar_producto(self, titulo: str) -> None:
        """Ultima barrera antes de postar: el producto vinculado tiene que ser el
        del registro. Uno parecido le manda la venta a otro lado."""
        if elegir_producto(titulo, self.textos()) is None:
            self.pasos.foto(self.d, "producto_no_coincide")
            raise PublicacionAbortada(f"El producto vinculado no es {titulo!r}")

    def escribir_legenda(self, legenda: str) -> None:
        self._tocar("Adicione legendas", contiene=True)
        self.d.send_keys(legenda, clear=True)
        _pausa()
        # Mientras se edita, la pantalla queda tapada por un velo y "OK" arriba a
        # la derecha: hasta tocarlo, nada de abajo responde (medido 2026-10-15).
        self._tocar("OK")

    def _interruptor_prendido(self, x: int, y: int) -> bool:
        r, g, b = self.d.screenshot().convert("RGB").getpixel((x, y))
        return es_verde(r, g, b)

    def marcar_rotulo_ia(self) -> None:
        """Los videos son de Google Flow: van con el rotulo de IA prendido.

        La app reporta `checked="false"` en todos sus interruptores, prendidos o
        no (medido), asi que el estado se lee del color: verde es prendido."""
        sw = self.d(resourceIdMatches=r".*:id/ai_generated_toggle")
        if not sw.wait(timeout=10):
            raise PublicacionAbortada("No encontre el interruptor del rotulo de IA")
        # Se mira el lado izquierdo: prendido, ahi esta la pista verde; apagado,
        # la bolita blanca. El centro no sirve, cae sobre la bolita en los dos.
        izq, arriba, _, abajo = sw.bounds()
        x, y = izq + 12, (arriba + abajo) // 2
        if not self._interruptor_prendido(x, y):
            sw.click()
            _pausa(1, 2)
        if not self._interruptor_prendido(x, y):
            self.pasos.foto(self.d, "rotulo_ia_apagado")
            raise PublicacionAbortada("El rotulo de IA no quedo prendido")

    def postar(self, aceptar_aviso: bool = False) -> None:
        self._tocar("Postar")
        # Shopee a veces avisa "Gostaria de reconsiderar postar isso?" (posible violacion
        # de pautas). Solo se acepta si Nick lo pidio para este video; si no, aborta.
        if self.d(textContains="reconsiderar postar").wait(timeout=5):
            self.pasos.foto(self.d, "aviso_pautas")
            if not aceptar_aviso:
                raise PublicacionAbortada("Shopee avisa de posible violacion de pautas")
            self.d(textStartsWith="Postar de").click()
        # Al publicar, la app sale de "Adicionar legenda". Si sigue ahi, no salio.
        time.sleep(15)
        self.pasos.foto(self.d, "despues_de_postar")
        if self.d(text="Adicionar legenda").exists:
            raise PublicacionAbortada("Despues de Postar la app sigue en la pantalla de publicar")

    def descartar(self) -> None:
        """Cerrar la app sin publicar: el borrador se pierde, y es lo que se quiere."""
        self.d.app_stop(PAQUETE)


def publicar(
    store: VideosStore,
    video: VideoProducido,
    celular: Celular,
    *,
    postar: bool,
    aceptar_aviso: bool = False,
    verificar: bool = True,
    pagina_directa: bool = False,
    carpeta: Path = CARPETA_VIDEOS,
) -> bool:
    """Sube un video. Con `postar=False` deja todo cargado, saca la captura y
    descarta: sirve para ver que el camino sigue andando sin publicar nada.
    Devuelve True solo si publico y lo marco como publicado."""
    assert video.legenda is not None  # siguiente_video ya lo garantiza
    celular.verificar_desbloqueado()
    celular.copiar_video(ruta_video(video.archivo, carpeta))
    celular.abrir_producto(video.link, video.titulo, pagina_directa=pagina_directa)
    celular.ir_a_shopee_video()
    celular.elegir_primer_video()
    if verificar:  # solo se salta si Nick confirmo a mano que el producto es el correcto
        celular.verificar_producto(video.titulo)
    celular.escribir_legenda(video.legenda)
    celular.marcar_rotulo_ia()
    celular.pasos.foto(celular.d, "listo_para_postar")
    if not postar:
        log.info("En seco: todo cargado para %s, no se publica", video.item_id)
        celular.descartar()
        return False
    celular.postar(aceptar_aviso)
    store.marcar_publicado(video.item_id, video.canal)
    log.info("Publicado %s (%s)", video.item_id, video.titulo)
    return True
