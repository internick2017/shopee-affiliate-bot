"""El catálogo de comandos del bot generador, en un solo lugar.

Existe porque la misma lista alimenta TRES cosas, y si cada una tuviera la suya se
desincronizarían y el menú terminaría mintiendo:

  1. el menú nativo de Telegram (lo que aparece al escribir "/"), vía `setMyCommands`;
  2. el texto de `/ayuda`;
  3. el aviso cuando alguien manda un comando que no existe.

El (3) nació de un caso real: escribir "/ ventas 90" con un espacio hace que Telegram
NO lo trate como comando, el mensaje cae en el manejador de texto suelto y el bot
contesta "no encontré ningún link de Shopee", que no tiene nada que ver con lo que la
persona pidió.
"""

from __future__ import annotations

from dataclasses import dataclass

from .bot_mensajes import esc


@dataclass(frozen=True)
class Comando:
    nombre: str          # sin la barra: Telegram la agrega
    descripcion: str     # una linea, la que se ve en el menu
    ejemplo: str = ""    # solo para /ayuda, donde si hay lugar


COMANDOS: tuple[Comando, ...] = (
    Comando("ideas", "Que grabar hoy: los mejores productos por categoria",
            "/ideas limpeza"),
    Comando("tendencia", "Que esta despegando AHORA, no lo que vendio siempre",
            "/tendencia 7"),
    Comando("video", "Referencia vertical 9:16 + prompt, a partir de un link",
            "/video <link> nativo"),
    Comando("ventas", "Cuanto entro de verdad, por banda de precio y por origen",
            "/ventas 90"),
    Comando("grabados", "Productos que ya usaste para video y no se repiten"),
    Comando("olvidar_video", "Volver a ofrecer un producto ya grabado",
            "/olvidar_video 12345678"),
    Comando("registrar_shopee", "Usar TUS credenciales de afiliado, no las compartidas"),
    Comando("olvidar_shopee", "Borrar tus credenciales y volver a las compartidas"),
    Comando("ayuda", "Esta lista"),
)


def comandos_para_telegram() -> list[tuple[str, str]]:
    """Lo que espera `set_my_commands`: pares (nombre, descripcion)."""
    return [(c.nombre, c.descripcion) for c in COMANDOS]


def texto_ayuda() -> str:
    lineas = ["<b>Que puedo hacer</b>", ""]
    for c in COMANDOS:
        lineas.append(f"/{c.nombre} - {esc(c.descripcion)}")
        if c.ejemplo:
            lineas.append(f"   <i>{esc(c.ejemplo)}</i>")
    lineas.append("")
    lineas.append("Tambien podes mandarme un link de Shopee suelto y te armo el post,")
    lineas.append("o un video y te lo dejo vertical 9:16.")
    return "\n".join(lineas)


def texto_desconocido(escrito: str) -> str:
    """Cuando el mensaje arranca con "/" pero no es un comando conocido."""
    return (
        f"No conozco {esc(escrito[:40])}.\n\n"
        "Ojo con el espacio despues de la barra: <code>/ ventas</code> no funciona, "
        "tiene que ser <code>/ventas</code>.\n\n"
        "Mira /ayuda para la lista completa."
    )


def parece_comando(texto: str | None) -> bool:
    """¿El usuario quiso mandar un comando aunque Telegram no lo reconozca?

    Existe por el caso que motivó todo esto: "/ ventas 90". Con el espacio, Telegram
    NO genera la entidad `bot_command`, así que `filters.COMMAND` no lo ve y el
    mensaje termina en el manejador de texto suelto, que responde sobre links.
    Detectarlo a mano es la única forma de contestar algo que tenga sentido.
    """
    return (texto or "").lstrip().startswith("/")
