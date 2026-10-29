"""Genera UN video en YouTube Create ("Gerar vídeo") con una imagen de la galeria del
celular y lo baja a la PC. Los videos de Lanny se hacen asi (Flow es para los de Nick).

Uso (desde la raiz del repo):
    python scripts/video/youtube_create.py <indice_galeria> <salida.mp4> "<prompt>"

`indice_galeria` es la posicion de la imagen en el selector de la app (0 = la mas nueva).
Sale con codigo 2 si la cuenta llego al limite ("Você alcançou o limite"): el cupo es por
cuenta Google, se cambia en "Menu da conta". Las capturas de cada paso quedan en
logs/youtube_create/. Toma el candado del celular (el de la cola de WhatsApp y Shopee Video).
Coordenadas medidas el 2026-10-29 en el Galaxy A07 (720x1600).
"""

from __future__ import annotations

import msvcrt
import os
import subprocess
import sys
import time
from pathlib import Path

import uiautomator2 as u2

RAIZ = Path(__file__).resolve().parents[2]
CAPTURAS = RAIZ / "logs" / "youtube_create"
PAQUETE = "com.google.android.apps.youtube.producer"


def adb(*args: str) -> str:
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    return subprocess.run(["adb", *args], capture_output=True, text=True, encoding="utf-8", env=env).stdout


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    idx, salida, prompt = int(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    candado = open(RAIZ / "logs" / "publicador.lock", "w")  # noqa: SIM115 abierto toda la corrida
    msvcrt.locking(candado.fileno(), msvcrt.LK_NBLCK, 1)
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    d = u2.connect()

    def foto(etq: str) -> None:
        d.screenshot(str(CAPTURAS / f"{salida.stem}_{etq}.png"))

    antes = set(adb("shell", "ls", "/sdcard/Download").splitlines())
    d.app_start(PAQUETE, stop=True)
    time.sleep(7)
    d.click(427, 684)  # Gerar vídeo
    time.sleep(3)
    d(description="Adicionar mídia").click(timeout=10)  # el boton se mueve con el teclado
    time.sleep(3)
    celda = d.xpath(f'//*[contains(@resource-id,"mediaThumbnail-{idx}")]')
    if celda.exists:
        celda.click()
    else:
        d.click([133, 360, 588][idx % 3], [425, 653, 880][idx // 3])
    time.sleep(2)
    foto("galeria")
    d(description="Concluído").click(timeout=10)
    time.sleep(2)
    d(className="android.widget.EditText").set_text(prompt)
    time.sleep(1)
    d.press("back")
    time.sleep(1)
    foto("prompt")
    d(description="Gerar").click(timeout=10)
    fin, estado = time.time() + 240, "timeout"
    while time.time() < fin:
        time.sleep(5)
        if d(description="Usar vídeo").exists:
            estado = "ok"
            break
        if d(textContains="limite").exists or d(descriptionContains="limite").exists:
            estado = "limite"
            break
        if d(textContains="Não é possível").exists or d(descriptionContains="Não é possível").exists:
            estado = "rechazado"
            break
    foto("resultado")
    print("ESTADO", estado)
    if estado != "ok":
        return 2
    d(description="Mais opções").click(timeout=10)
    time.sleep(2)
    d(description="Salvar no dispositivo").click(timeout=10)
    time.sleep(3)
    botones = d.xpath('//*[@content-desc="Salvar no dispositivo"]').all()
    if botones:
        botones[-1].click()
    nuevos: set[str] = set()
    for _ in range(30):
        time.sleep(2)
        nuevos = {n for n in set(adb("shell", "ls", "/sdcard/Download").splitlines()) - antes if n.endswith(".mp4")}
        if nuevos:
            break
    if not nuevos:
        foto("sin_guardar")
        print("No aparecio el archivo guardado")
        return 1
    time.sleep(2)
    adb("pull", "/sdcard/Download/" + sorted(nuevos)[-1], str(salida))
    print("BAJADO", salida)
    d.press("home")
    return 0


if __name__ == "__main__":
    sys.exit(main())
