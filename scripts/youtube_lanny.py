"""Sube los videos de Lanny a su canal de YouTube ("Lanny Herrera") por la API.

Uso:
    python scripts/youtube_lanny.py autorizar              # imprime el enlace (una sola vez)
    python scripts/youtube_lanny.py autorizar <codigo>     # guarda el permiso del canal
    python scripts/youtube_lanny.py pendientes             # videos de Lanny que faltan en YouTube
    python scripts/youtube_lanny.py subir <item_id> --simular   # muestra titulo, texto y link
    python scripts/youtube_lanny.py subir <item_id> [--privado] # sube, guarda y comenta el link
    python scripts/youtube_lanny.py rescatar <item_id> <video_id> <link>  # subio pero no guardo

Autorizar: abrir el enlace en el Chrome donde esta la sesion de herreralanny@gmail.com,
elegir esa cuenta, aceptar, y copiar el `code=` de la URL a la que vuelve (localhost no
carga, es normal). El codigo vence en minutos y sirve una sola vez.

La app OAuth es la de Setup Justo (proyecto `setup-justo`, decision de Nick 2026-10-29):
`YOUTUBE_CLIENT_ID` y `YOUTUBE_CLIENT_SECRET` se leen del `.env` del bot y, si no estan,
del `.env` de home-office-br, para no duplicar el secreto.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path

BOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BOT))

from dotenv import dotenv_values, load_dotenv  # noqa: E402

from src import canal_youtube  # noqa: E402
from src.grabados_store import PublicacionesStore, VideosStore  # noqa: E402
from src.video_canal import link_del_canal  # noqa: E402
from src.youtube_lanny import (  # noqa: E402
    CANAL,
    PLATAFORMA,
    TOKEN,
    NoSePublico,
    comentario,
    descripcion,
    pendientes,
    publicar,
    resolver_archivo,
    titulo,
)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HOME_OFFICE_ENV = Path(r"E:\dev\01-web-apps\home-office-br\.env")
ENTREGADOS = BOT / "videos_entregados" / "shopee-video-flow"
REDIRECT = "http://localhost:8080"  # el mismo que tiene registrado la app de Setup Justo


def _cliente_oauth() -> tuple[str, str]:
    otro = dotenv_values(HOME_OFFICE_ENV) if HOME_OFFICE_ENV.is_file() else {}
    cid = os.getenv("YOUTUBE_CLIENT_ID") or otro.get("YOUTUBE_CLIENT_ID")
    sec = os.getenv("YOUTUBE_CLIENT_SECRET") or otro.get("YOUTUBE_CLIENT_SECRET")
    if not cid or not sec:
        sys.exit("Faltan YOUTUBE_CLIENT_ID y YOUTUBE_CLIENT_SECRET (.env del bot o de home-office-br)")
    return cid, sec


def _video(store: VideosStore, item_id: int):
    for v in store.listar(canal=CANAL, cuantos=1000):
        if v.item_id == item_id:
            return v
    sys.exit(f"No hay video de {CANAL} con item_id {item_id} en videos_producidos")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("autorizar")
    a.add_argument("codigo", nargs="?")
    sub.add_parser("pendientes")
    s = sub.add_parser("subir")
    s.add_argument("item_id", type=int)
    s.add_argument("--privado", action="store_true")
    s.add_argument("--simular", action="store_true", help="no toca YouTube")
    r = sub.add_parser("rescatar")
    r.add_argument("item_id", type=int)
    r.add_argument("video_id")
    r.add_argument("link")
    args = p.parse_args()

    load_dotenv(BOT / ".env")
    db = os.getenv("GRABADOS_DB") or str(BOT / "grabados.db")
    pubs = PublicacionesStore(db)

    if args.cmd == "autorizar":
        cid, sec = _cliente_oauth()
        if not args.codigo:
            print("Abri este enlace con la cuenta de Lanny y volve con el code= de la URL:\n")
            print(canal_youtube.url_de_autorizacion(cid, REDIRECT))
            print("\nDespues: python scripts/youtube_lanny.py autorizar <codigo>")
            return 0
        tokens = canal_youtube.autorizar(args.codigo, cid, sec, REDIRECT)
        if not tokens:
            sys.exit("Google rechazo el codigo. Suele estar vencido: pedi uno nuevo.")
        pubs.guardar_credencial(TOKEN, tokens[1])
        print("Canal autorizado.")
        return 0

    if args.cmd == "rescatar":
        pubs.registrar(args.item_id, canal=CANAL, plataforma=PLATAFORMA,
                       id_externo=args.video_id, link=args.link)
        print(f"Guardado: {args.item_id} = https://youtube.com/shorts/{args.video_id}")
        return 0

    videos = VideosStore(db)
    if args.cmd == "pendientes":
        lista = pendientes([resolver_archivo(v, ENTREGADOS)
                            for v in videos.listar(canal=CANAL, cuantos=1000)],
                           pubs.ids_publicados(CANAL, PLATAFORMA))
        for v in lista:
            visto = "visto" if v.fidelidad_ts else "     "
            print(f"{v.item_id:>12}  {visto}  {Path(v.archivo).name:<40} {titulo(v)}")
        print(f"\n{len(lista)} pendientes")
        return 0

    video = resolver_archivo(_video(videos, args.item_id), ENTREGADOS)

    def generar_link(item_id: int) -> str:
        return link_del_canal(item_id, CANAL, plataforma=PLATAFORMA)

    if args.simular:
        link = generar_link(video.item_id)
        print(f"Archivo: {video.archivo}\nTitulo: {titulo(video)}\n")
        print(f"Descripcion:\n{descripcion(video, link)}\n\nComentario: {comentario(link)}")
        return 0

    cid, sec = _cliente_oauth()

    def access_token() -> str | None:
        refresh = pubs.credencial(TOKEN)
        if not refresh:
            sys.exit("El canal no esta autorizado: corre 'autorizar'")
        return canal_youtube.renovar_token(refresh, cid, sec)

    try:
        res = publicar(video, pubs, generar_link=generar_link, access_token=access_token,
                       subir=canal_youtube.subir_short, comentar=canal_youtube.comentar,
                       privado=args.privado)
    except NoSePublico as exc:
        sys.exit(f"No se publico: {exc}")
    print(f"Subido{' (privado)' if args.privado else ''}: https://youtube.com/shorts/{res.video_id}")
    print(f"Link: {res.link}")
    print("Comentario con el link: " + ("listo (fijarlo a mano en Studio)" if res.comentado
                                        else "FALLO, ponerlo a mano"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
