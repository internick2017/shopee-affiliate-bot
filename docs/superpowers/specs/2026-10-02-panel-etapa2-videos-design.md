# Panel de reportes, etapa 2: videos a fondo

Fecha: 2026-10-02. Estado: diseño aprobado por partes en el chat, pendiente de revisión
del documento completo.

Sigue a `2026-10-02-panel-reportes-design.md` (etapa 1, ventas), que ya está publicada en
https://panel-afiliados.vercel.app. Esta etapa vuelve útil la pestaña Vídeos para dos
cosas, con el mismo peso:

1. **Controlar la publicación.** Saber qué video falta publicar y marcarlo como publicado
   desde el celular, sin pasar por el chat.
2. **Saber qué rinde.** Qué videos venden, cuál herramienta y cuál canal rinden más, si la
   comisión que prometía Shopee al grabar se cumple, y cuánto tarda un video en vender.

## Por qué ahora

La lista "Para publicar" de la etapa 1 muestra 59 videos de Lanny pendientes (17 de 76
marcados), y casi todos ya salieron. La marca solo existe si alguien se lo dice al chat.
Con ese dato roto, ni el control ni las métricas de tiempo sirven. Por eso el corazón de
la etapa es que la marca se pueda poner donde se publica: en el celular.

### Criterios de éxito

- Lanny marca un video suyo como publicado desde el panel y, en la siguiente
  sincronización, la skill `shopee-video-flow` deja de listarlo como pendiente.
- Lanny no puede marcar ni desmarcar un video de la cuenta de Nick. Verificado contra la
  base real, no leyendo las políticas.
- Ninguna sincronización borra una marca ya puesta.
- La vista Desempenho responde las cinco preguntas de abajo con los datos reales.

## Decisiones tomadas en el chat

- La marca se pone con un botón en el panel (opción A), aunque eso cambia la regla de la
  etapa 1 de que el panel solo lee. Se escribe en una **tabla aparte** (opción 1): la
  sincronización existente nunca toca lo que escribe el panel.
- El archivo del video sigue pasando de la PC al celular por WhatsApp. El panel no
  almacena videos (opción B): el plan gratis de Supabase tiene 1 GB y el traspaso no es
  el problema a resolver ahora.
- Setup Justo queda fuera de Desempenho: sus videos van a YouTube y Facebook, no a Shopee
  Video, y sus ventas no se separan con la misma regla. Va en la etapa 3.

## Datos

### Lo que ya existe

La tabla `video` (migración 0001) ya trae `precio`, `comision_pct`, `herramienta`,
`grabado_en` y `publicado_en`, y `sync_panel.py` ya los sube. Los 149 videos tienen
precio y comisión cargados. `comision_pct` es un porcentaje (8.0 = 8%). El panel no los
usaba; solo falta sumarlos al tipo `Video` de `lib/tipos.ts`.

### Migración `0002_publicacao.sql`

```sql
create table publicacao (
  canal        text not null,
  item_id      bigint not null,
  publicado_en timestamptz not null default now(),
  marcado_por  uuid not null default auth.uid() references auth.users (id),
  primary key (canal, item_id),
  foreign key (canal, item_id) references video (canal, item_id)
);
```

Una fila por video marcado desde el panel. La clave primaria hace que dos marcas del mismo
video no se dupliquen: el panel inserta con "si ya existe, no hacer nada", y vale la
primera.

**Permisos y reglas (RLS):**

- `grant select, insert, delete on publicacao to authenticated`; todo a `service_role`;
  nada a `anon`. Sin `update`: una marca se crea o se borra, no se edita.
- Leer: las filas de videos de mis cuentas, o todas si soy admin.
- Crear: solo si el video es de una de mis cuentas (o soy admin) y `marcado_por` es mi
  usuario.
- Borrar: las mismas condiciones, y además solo si `video.publicado_en` sigue vacío. Una
  vez que la marca llegó a la PC y volvió en `video`, ya no se deshace desde el panel.

De paso entra el pendiente de la revisión de la etapa 1: `revoke all on` las tablas del
panel `from anon`, para no depender de que el proyecto se creó sin exponer tablas.

## Sincronización (`sync_panel.py`)

La parte de videos de `sincronizar` pasa a tener dos pasos, en este orden:

1. **Traer las marcas.** Lee `publicacao` entera con la llave de servicio. Por cada fila,
   si ese video existe en `grabados.db` y todavía no está publicado, le pone
   `publicado_ts` = la fecha de la marca. Si ya estaba publicado, no lo toca (gana la
   fecha más vieja, que es la real). Si el video no existe en la PC, lo anota en el log y
   sigue.
2. **Subir los videos** como hoy. Como el paso 1 ya dejó las marcas en `grabados.db`,
   `publicado_en` sube completo.

`VideosStore` necesita marcar sin pisar: un `marcar_publicado` que no cambie un video ya
publicado (variante nueva o parámetro; lo decide el plan). El `marcar_publicado` que usa
el chat sigue como está.

**Si falla el paso 1** (Supabase caído, error de permisos): la corrida sube los videos
igual y registra la parte de videos como fallida en `sincronizacion`, con el error. El
punto rojo del Início lo muestra.

### Cómo decide el panel si un video está publicado

`publicado = video.publicado_en ?? publicacao.publicado_en`. Lo primero es lo confirmado
en la PC; lo segundo, lo marcado en el panel que todavía no pasó por la PC (como mucho 4
horas). Mientras solo exista en `publicacao`, se puede deshacer.

## Pantallas

La pestaña Vídeos pasa a tener dos vistas, con un selector arriba: **Publicar** y
**Desempenho**. Las dos respetan la cuenta elegida (Lanny, Nick, Tudo). Solo entran los
canales `lanny` y `nick`.

### Publicar

- Lista de videos sin publicar: producto, archivo, canal, link y botón **"Publicado"**.
- Al tocarlo, la fila muestra "Publicado agora · Desfazer". "Desfazer" se ve mientras la
  marca solo está en `publicacao`.
- **"Selecionar vários"**: casillas y un botón "Marcar N como publicados", con
  confirmación. Es para ponerse al día con los videos ya publicados de Lanny.
- Abajo, plegada, la lista "Publicados recentemente" (últimos 7 días).
- Si guardar falla (sin señal, sesión vencida): la fila vuelve a su estado y aparece
  "Não foi possível marcar. Tente de novo." Nunca se muestra publicado algo que no se
  guardó.

### Desempenho

Usa el mismo selector de período del Início (compartido por el contexto).

1. **Tarjetas:** videos publicados; % que ya vendieron; comisión vía video; días típicos
   (mediana) hasta la primera venta.
2. **Ranking de videos:** comisión y ventas vía video, ventas por otros orígenes como dato
   secundario, días hasta la primera venta. Los 10 primeros y "ver todos".
3. **Flow vs Flow Music:** por herramienta, cantidad de videos, % con venta y comisión
   promedio por video.
4. **Por canal:** lo mismo, lanny contra nick.
5. **Prometido vs real:** por video, `comision_pct` contra la tasa real (comisión sobre
   lo vendido de sus ventas vía video); el promedio general; los de mayor diferencia.
6. **Sin ventas:** publicados hace más de 14 días que nunca vendieron vía video.

### Reglas de cálculo

- **Venta del video:** una venta del mismo producto (`cuenta`, `item_id`), con origen
  Shopee Video, no cancelada, con `compra_en` igual o posterior a la publicación. Si el
  video no tiene fecha de publicación, cuenta desde que se grabó (`grabado_en`), porque
  antes de grabarlo seguro no existía.
- **Días hasta la primera venta, "sin ventas" y "% que vendieron":** solo videos con fecha
  de publicación. Sin ella no hay desde cuándo contar.
- **Herramienta:** se agrupa por prefijo. "Flow Music" es Flow Music; cualquier otra que
  empiece con "Flow" (incluida "Flow (I2V desde imagen validada)") es Flow.
- **Tasa real:** `sum(comision) / sum(precio * cantidad)` de las ventas del video. Sin
  ventas, no se compara.
- **Período:** filtra las ventas, no los videos. Un video viejo aparece si vendió en el
  período.

Todo esto vive en un archivo de cuentas puras (`lib/videos.ts`), con tests, igual que
`calculos.ts` y `periodo.ts`.

## Fuera de alcance, a propósito

- Guardar o descargar videos desde el panel.
- Desmarcar desde el panel una marca ya confirmada en la PC (se hace por el chat).
- Setup Justo (etapa 3) y qué grabar después (etapa 4).
- Notificaciones.

## Pruebas

- **Bot (pytest):** traer marcas marca un video sin publicar, no toca uno publicado,
  saltea uno desconocido y lo informa; las marcas se aplican antes de subir los videos;
  una falla al leer marcas no frena la subida y queda registrada.
- **Panel (vitest), `lib/videos.ts`:** venta anterior a la publicación no cuenta; video
  sin fecha de publicación; días hasta la primera venta; tasa real contra prometida;
  agrupación de herramientas; período que filtra ventas y no videos.
- **Base real:** `scripts/verificar_acceso_panel.py` suma: un usuario marca un video suyo
  (puede), uno ajeno (rechazado), desmarca uno ajeno (rechazado), desmarca uno suyo ya
  confirmado (rechazado), y sin sesión no puede nada. Limpia lo que crea.
- **A mano en el navegador:** marcar, deshacer, marcar varios y Desempenho, con un usuario
  temporal que se borra al terminar.
