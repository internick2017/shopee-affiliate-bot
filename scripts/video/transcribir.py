"""Transcribe la narracion de un video de Flow y avisa si promete cosas de salud.

Uso:
    python transcribir.py video.mp4
    python transcribir.py video.mp4 --modelo base     # mas rapido, menos preciso

Por que existe: la narracion la inventa el modelo de video, no el prompt. Con productos de
salud, medicos, ortopedicos, fitness, suplementos o cosmeticos, una promesa de cura,
tratamiento o prevencion de enfermedades viola la ley sanitaria (Anvisa) y la politica de
Shopee Video ("informacoes enganosas sobre saude"). Por eso el audio se revisa siempre antes
de entregar, no solo los fotogramas.

El chequeo de terminos es una AYUDA, no un veredicto: marca lo que hay que mirar con atencion.
Leer siempre la transcripcion completa.
"""

import argparse
import sys
import unicodedata

# Terminos que, en un video de producto, sugieren una promesa de salud prohibida.
# Van sin acentos: el texto se normaliza antes de comparar.
TERMINOS_RIESGO = [
    "cura", "curar", "cure",
    "trata", "tratar", "tratamento", "terapia", "terapeutico",
    "previne", "prevenir", "prevencao",
    "doenca", "doencas", "enfermidade",
    "sintoma", "sintomas",
    "diagnostic",
    "remedio", "medicamento",
    "covid", "asma", "bronquite", "pneumonia", "enfisema", "dpoc",
    "recupera", "reabilita",
    "milagre", "milagroso",
    "emagrece", "emagrecimento",
    "receita medica", "prescricao",
]


def sin_acentos(texto: str) -> str:
    desarmado = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in desarmado if unicodedata.category(c) != "Mn")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archivo", help="video o audio a transcribir")
    ap.add_argument("--modelo", default="small",
                    help="tiny, base, small (default), medium, large-v3")
    ap.add_argument("--idioma", default="pt", help="codigo de idioma (default: pt)")
    args = ap.parse_args()

    # La consola de Windows viene en cp1252 y se come los acentos del portugues.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    from faster_whisper import WhisperModel

    modelo = WhisperModel(args.modelo, device="cpu", compute_type="int8")
    segmentos, info = modelo.transcribe(args.archivo, language=args.idioma, vad_filter=False)

    partes = []
    print(f"--- transcripcion ({args.modelo}, {info.language}) ---")
    for seg in segmentos:
        print(f"[{seg.start:5.1f}s - {seg.end:5.1f}s] {seg.text.strip()}")
        partes.append(seg.text)

    texto = sin_acentos(" ".join(partes))
    if not texto.strip():
        print("\n[!] No se detecto habla. Revisar que el video tenga narracion.")
        return 1

    encontrados = sorted({t for t in TERMINOS_RIESGO if sin_acentos(t) in texto})

    print("\n--- chequeo de promesas de salud ---")
    if encontrados:
        print("[!] REVISAR A MANO. Aparecen estos terminos:", ", ".join(encontrados))
        print("    Si la narracion promete curar, tratar o prevenir una enfermedad,")
        print("    o nombra una enfermedad, el video NO se entrega: se regenera.")
        return 2

    print("[ok] Sin terminos de riesgo. Leer igual la transcripcion de arriba antes de entregar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
