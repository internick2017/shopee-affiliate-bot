"""Le manda a Lanny por WhatsApp, desde el celular, los videos del dia: cada uno en HD con su
legenda como leyenda y despues el link aparte (formato que aprobo Nick el 2026-10-23).

Uso (desde la raiz del repo):
    python scripts/video/mandar_a_lanny.py --texto "Seguem os vídeos de hoje"
    python scripts/video/mandar_a_lanny.py copos_versalhes chave_impacto ...      # en seco
    python scripts/video/mandar_a_lanny.py copos_versalhes chave_impacto --enviar

Cada nombre es el de `videos_entregados/shopee-video-flow/<nombre>_lanny.mp4`; link y legenda
salen de `videos_producidos` (canal lanny). Sin --enviar deja todo listo, saca captura y
descarta sin mandar. Toma el candado del celular: respetar los horarios de la cola del grupo.

Medido el 2026-10-29 en el Galaxy A07: el contacto se elige por texto EXACTO "Lanny" (el grupo
"#1 Nosso Grupo | Lanny" tambien lo contiene); la miniatura abre el editor; HD se prende ANTES
de la leyenda (con el teclado abierto el boton queda tapado); la leyenda necesita un click
antes de `set_text` o no queda.
"""

from __future__ import annotations

import argparse
import msvcrt
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import uiautomator2 as u2

RAIZ = Path(__file__).resolve().parents[2]
ENTREGA = RAIZ / "videos_entregados" / "shopee-video-flow"
CAPTURAS = RAIZ / "logs" / "mandar_a_lanny"
CARPETA_CELULAR = "/sdcard/Download/lanny"
CONTACTO = "Lanny"
WA = "com.whatsapp"


class Fallo(RuntimeError):
    pass


def adb_shell(*args: str) -> str:
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    return subprocess.run(["adb", "shell", *args], capture_output=True, text=True,
                          encoding="utf-8", env=env).stdout


class Envio:
    def __init__(self, d, enviar: bool):
        self.d, self.enviar = d, enviar

    def foto(self, etq: str) -> None:
        self.d.screenshot(str(CAPTURAS / f"{time.strftime('%H%M%S')}_{etq}.png"))

    def compartir(self, *extras: str) -> None:
        adb_shell("am", "start", "-a", "android.intent.action.SEND", *extras, "-p", WA)
        fila = self.d(text=CONTACTO, resourceId=f"{WA}:id/contactpicker_row_name")
        if not fila.wait(timeout=15):
            self.foto("sin_contacto")
            raise Fallo(f"No aparecio {CONTACTO!r} para compartir")
        fila.click()
        time.sleep(2)

    def mandar_o_descartar(self, etq: str) -> None:
        if not self.d(text=CONTACTO).exists:
            raise Fallo("El destinatario no es Lanny")
        self.foto(etq)
        if self.enviar:
            self.d(resourceId=f"{WA}:id/send").click(timeout=10)
            time.sleep(5)
            return
        self.d.press("back")
        if self.d(text="Descartar").wait(timeout=5):
            self.d(text="Descartar").click()
        self.d.press("back")

    def texto(self, mensaje: str) -> None:
        self.compartir("-t", "text/plain", "--es", "android.intent.extra.TEXT", f"'{mensaje}'")
        self.mandar_o_descartar("texto")

    def video(self, archivo: Path, legenda: str) -> None:
        destino = f"{CARPETA_CELULAR}/{archivo.name}"
        self.d.push(str(archivo), destino)
        adb_shell("am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE", "-d", f"file://{destino}")
        self.compartir("-t", "video/mp4", "--eu", "android.intent.extra.STREAM", f"file://{destino}")
        self.d(resourceId=f"{WA}:id/thumbnail").click(timeout=10)
        time.sleep(3)
        calidad = self.d(resourceId=f"{WA}:id/media_upload_quality_settings")
        if "Desativada" in calidad.info["contentDescription"]:
            calidad.click()
            time.sleep(2)
            self.d(resourceId=f"{WA}:id/media_quality_hd").click(timeout=10)
            time.sleep(2)
        if "Ativada" not in calidad.info["contentDescription"]:
            raise Fallo("HD no quedo prendido")
        caja = self.d(resourceId=f"{WA}:id/caption")
        caja.click()
        time.sleep(1)
        caja.set_text(legenda)
        time.sleep(1)
        if self.d(description="Barra de espaço").exists:
            self.d.press("back")
            time.sleep(1)
        if not (caja.get_text() or "").startswith(legenda[:20]):
            raise Fallo("La legenda no quedo puesta")
        self.mandar_o_descartar(archivo.stem)


def link_y_legenda(nombre: str) -> tuple[str, str]:
    db = sqlite3.connect(RAIZ / "grabados.db")
    fila = db.execute(
        "SELECT link, legenda FROM videos_producidos WHERE canal = 'lanny' AND archivo LIKE ? "
        "ORDER BY ts DESC LIMIT 1", (f"%{nombre}_lanny.mp4",)).fetchone()
    if not fila or not fila[0] or not fila[1]:
        raise Fallo(f"{nombre}: sin link o sin legenda en videos_producidos")
    return fila[0], fila[1]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("nombres", nargs="*")
    ap.add_argument("--texto", help="manda solo este mensaje")
    ap.add_argument("--enviar", action="store_true", help="mandar de verdad (sin esto, en seco)")
    args = ap.parse_args()
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    candado = open(RAIZ / "logs" / "publicador.lock", "w")  # noqa: SIM115 abierto toda la corrida
    msvcrt.locking(candado.fileno(), msvcrt.LK_NBLCK, 1)
    envio = Envio(u2.connect(), args.enviar)
    if args.texto:
        envio.texto(args.texto)
    for nombre in args.nombres:
        link, legenda = link_y_legenda(nombre)
        archivo = ENTREGA / f"{nombre}_lanny.mp4"
        if not archivo.is_file():
            raise Fallo(f"Falta {archivo}")
        envio.video(archivo, legenda)
        time.sleep(3)
        envio.texto(link)
        print(("ok " if args.enviar else "en seco ") + nombre)
        time.sleep(5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
