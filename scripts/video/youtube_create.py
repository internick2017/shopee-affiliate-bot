"""Genera UN video en YouTube Create ("Gerar vídeo") con una imagen de la galeria del
celular y lo baja a la PC. Los videos de Lanny se hacen asi (Flow es para los de Nick).

Uso (desde la raiz del repo):
    python scripts/video/youtube_create.py <indice_galeria> <salida.mp4> "<prompt>" [gancho] [item_id] [imagen.jpg]

`indice_galeria` es la posicion de la imagen en el selector de la app (0 = la mas nueva).
Pasar siempre `imagen.jpg`, la que debe usarse: sale con codigo 4 sin generar si la elegida es otra.
Sale con codigo 3 si la imagen del video baja mas corta que el audio, y con codigo 2 si la cuenta llego al limite ("Você alcançou o limite"): el cupo es por
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
sys.path.insert(0, str(RAIZ))

from src.grabados_store import IntentosStore  # noqa: E402

CAPTURAS = RAIZ / "logs" / "youtube_create"
PAQUETE = "com.google.android.apps.youtube.producer"


def adb(*args: str) -> str:
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    return subprocess.run(["adb", *args], capture_output=True, text=True, encoding="utf-8", env=env).stdout


def duracion(archivo: Path, stream: str) -> float:
    """Segundos de un stream ("v" o "a"), copiandolo sin re-encodear."""
    import re

    import imageio_ffmpeg

    salida = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(archivo),
                             "-map", f"0:{stream}?", "-c", "copy", "-f", "null", "-"],
                            capture_output=True, text=True, errors="replace").stderr
    t = re.findall(r"time=(\d+):(\d+):([\d.]+)", salida)
    return int(t[-1][0]) * 3600 + int(t[-1][1]) * 60 + float(t[-1][2]) if t else 0.0


MAX_DIFERENCIA = 55  # medido 2026-10-31: misma imagen 33, otra imagen 81 a 85


def diferencia_miniatura(captura: Path, imagen: Path) -> float:
    """Cuanto difiere la miniatura de la pantalla del prompt contra la imagen que debia usarse."""
    from PIL import Image, ImageChops, ImageStat

    pantalla = Image.open(captura).convert("RGB")
    img = Image.open(imagen).convert("RGB")
    w, h = img.size
    lado = min(w, h)
    x, y = (w - lado) // 2, (h - lado) // 2
    borde = lado // 20
    ref = img.crop((x + borde, y + borde, x + lado - borde, y + lado - borde)).resize((48, 48))
    # la miniatura cambia de lugar segun la cuenta: interfaz vieja e interfaz nueva
    zonas = ((60, 1165, 225, 1330), (40, 1025, 170, 1155))
    minis = (pantalla.crop(z).resize((48, 48)) for z in zonas)
    return min(sum(ImageStat.Stat(ImageChops.difference(m, ref)).mean) / 3 for m in minis)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    idx, salida, prompt = int(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    gancho = sys.argv[4] if len(sys.argv) > 4 else "sin gancho"
    item_id = int(sys.argv[5]) if len(sys.argv) > 5 else None
    esperada = Path(sys.argv[6]) if len(sys.argv) > 6 else None
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
    # el boton se mueve con el teclado; sin imagen previa en la sesion se llama distinto (2026-10-30)
    boton = d(description="Adicionar mídia")
    if not boton.exists(timeout=3):
        boton = d(description="Fazer upload de até 3 imagens")
    boton.click(timeout=10)
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
    if esperada and diferencia_miniatura(CAPTURAS / f"{salida.stem}_prompt.png", esperada) > MAX_DIFERENCIA:
        # el indice 0 es la foto mas nueva del celular, y por WhatsApp entran fotos personales
        print("ABORTADO: la imagen elegida no es la esperada, no se genera nada")
        return 4
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
    IntentosStore(RAIZ / "grabados.db").registrar(
        salida.stem, herramienta="YouTube Create", prompt=prompt, estado=estado,
        gancho=gancho, item_id=item_id)
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
    # La app reserva el tamano final del archivo antes de terminar de escribirlo: copiarlo
    # enseguida dejo 4 videos con la imagen cortada (2026-10-29). Esperar a que deje de crecer.
    origen = "/sdcard/Download/" + sorted(nuevos)[-1]
    anterior = ""
    for _ in range(30):
        time.sleep(3)
        actual = adb("shell", "stat", "-c", "%s %Y", origen).strip()
        if actual and actual == anterior:
            break
        anterior = actual
    time.sleep(5)
    adb("pull", origen, str(salida))
    d.press("home")
    # 2026-10-29: 4 de 6 videos bajaron con la imagen cortada a ~4,8 s y el audio a 10 s
    # (el ultimo cuadro queda quieto y la voz sigue). Copiado de nuevo despues, estaba
    # entero: se vuelve a copiar hasta 3 veces, y si sigue cortado no se entrega.
    imagen, audio = duracion(salida, "v"), duracion(salida, "a")
    for _ in range(3):
        if imagen >= audio - 0.5:
            break
        time.sleep(15)
        adb("pull", origen, str(salida))
        imagen, audio = duracion(salida, "v"), duracion(salida, "a")
    if imagen < audio - 0.5:
        print(f"CORTADO imagen {imagen:.1f} s, audio {audio:.1f} s: volver a generar", salida)
        return 3
    print("BAJADO", salida, f"imagen {imagen:.1f} s, audio {audio:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
