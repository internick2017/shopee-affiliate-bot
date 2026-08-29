# Glosario del dominio — shopee-affiliate-bot

## Bot generador de posts

Bot de Telegram (`python-telegram-bot`, proceso separado de `run_ofertas.py`/Telethon)
que un usuario whitelisted usa en chat privado: pega un link de Shopee (afiliado o
crudo) y el bot le devuelve un **post propio** listo (foto + caption) para publicar
a mano. No publica solo — distinto del pipeline de auto-post/revisión existente
(`ReviewPipeline`, `ChannelPoster`), que corre sobre las fuentes reenviadas al canal.

## Whitelist de acceso

Lista de `user_id` de Telegram permitidos para usar el bot generador, en
`BOT_ALLOWED_USERS` (`.env`). Existe desde el MVP para que la decisión de a quién
se le abre el bot (y si se cobra) quede en manos del operador más adelante, sin
tener que rearquitecturar el control de acceso después.

## Candado de instancia única

Archivo bloqueado por el sistema operativo (`ofertas.lock`, `generador.lock`) que
cada bot toma al arrancar; si ya lo tiene otro proceso, el bot no arranca
(`src/instancia_unica.py`). Existe porque los bots los levanta una tarea programada
que se reintenta **cada 2 minutos**, y el `MultipleInstances=IgnoreNew` de Windows
solo conoce las instancias que arrancó esa misma tarea: no ve un bot lanzado a mano
con los `.vbs`. Sin el candado se midieron dos `run_ofertas.py` corriendo a la vez,
o sea cada oferta publicada dos veces en el canal.

Es un bloqueo del SO y no un archivo con el PID adentro a propósito: si el bot
crashea o se corta la luz, el bloqueo se libera solo y la tarea lo puede volver a
levantar. Un archivo con el PID quedaría trabado para siempre.

## Modos de personas en el prompt de video

Los tres valores que acepta `/video` para decidir quién puede aparecer:
`sin` (default, solo el producto), `manos` (manos sin caras) y `personas` (una
persona adulta). El default es `sin` porque las manos son lo que peor generan los
modelos de video. Es independiente del eje `nativo`, que decide el formato de
salida. La prohibición de niños y bebés no es un modo: va en las tres variantes y
ningún modificador la levanta.
