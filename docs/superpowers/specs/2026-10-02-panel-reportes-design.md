# Panel de reportes de afiliados (etapa 1: ventas)

Fecha: 2026-10-02. Estado: diseño aprobado por partes en el chat, pendiente de revisión
del documento completo.

## Para qué existe

Nick y Lanny venden como afiliados de Shopee, cada uno con su cuenta. Hoy los números se
ven solo pidiéndolos: `/ventas` en el bot de Telegram o un script suelto. El panel junta
todo en un solo lugar que se abre desde el celular, con un usuario para cada uno.

Lo que pidió Nick, textual en espíritu: "todo lo que se pueda", una manera general de
controlar lo de él y lo de Lanny. Se parte en etapas para que cada una funcione sola:

1. **Ventas** (este documento): plata completada, pendiente y cancelada, por cuenta, por
   mes y por origen; y qué video terminó en venta.
2. Videos a fondo: producción, publicación, links.
3. Setup Justo: Shorts de YouTube, posts de Facebook, catálogo.
4. Qué grabar después: tendencias y la fórmula de `/ideas` contra lo que vendió.

Las etapas 2 a 4 no se diseñan acá; el modelo de datos solo les deja lugar.

### Criterios de éxito de la etapa 1

- Nick abre el panel en el celular y ve las ventas de las dos cuentas, juntas o por
  separado, sin pedirle nada a nadie.
- Lanny entra con su usuario y ve solo lo suyo. Verificado con una prueba real, no
  supuesto.
- Una venta pendiente que Shopee completa aparece completada en el panel en menos de 4
  horas (con la PC de Nick prendida).
- Las ventas de más de 90 días siguen visibles. Hoy la API de Shopee las deja de
  devolver y se pierden.

### Supuestos (no los dijo Nick, se tomaron por defecto)

- Es de uso privado de Nick y Lanny, no un sitio público.
- Nick ve todo; Lanny ve solo su cuenta.
- Solo muestra: no cambia nada en Shopee ni en las bases del bot.

## Enfoque elegido: sincronizar a la nube, el panel solo lee

Se compararon tres caminos. Elegido el A.

| | A. Sincronizar y leer | B. Panel que consulta Shopee en vivo | C. Google Sheets + Looker Studio |
|---|---|---|---|
| Claves de Shopee | Quedan en la PC | Pasan a la nube | Quedan en la PC |
| Toca el bot | No | Sí (videos a Supabase) | No |
| Historial > 90 días | Sí | No | Sí |
| Frescura | Hasta 4 h | Al instante | Hasta 4 h |
| Depende de la PC | Sí | No | Sí |
| Separar por usuario | Lo hace la base | A mano | Difícil |

A es el único que cumple celular + usuario para Lanny + todo junto sin tocar el bot. Si
más adelante molesta depender de la PC, la parte de Shopee se puede mover a GitHub
Actions (como la sincronización de Setup Justo) sin rehacer el panel.

## Piezas

```
Shopee API (2 cuentas) ─┐
                        ├─> sync_panel.py (PC de Nick, cada 4 h) ─> Supabase ─> Panel (Vercel) ─> celular
grabados.db (videos) ───┘
```

### 1. Sincronizador: `sync_panel.py`, en el repo del bot

- Vive en `shopee-affiliate-bot` porque ahí ya están las claves de Shopee (`.env`), el
  código que habla con la API (`src/shopee_resolver._graphql_call`) y `grabados.db`
  (`src/grabados_store.VideosStore`). Se reusan, no se copian.
- Corre cada 4 horas con una tarea programada de Windows, el mismo mecanismo que los
  bots (`instalar-tareas.ps1`).
- Escribe en Supabase con la llave de servicio, que vive solo en el `.env` de la PC.
- Se separa en dos partes para poder probarlo:
  - **Transformar** (puro, sin red): respuesta de Shopee a filas de `venta`; filas de
    `videos_producidos` a filas de `video`.
  - **Escribir** (con red): upsert en Supabase y registro en `sincronizacion`.

### 2. Base: un proyecto nuevo de Supabase

- Separado del de Setup Justo: aquel alimenta un sitio público, este guarda las
  finanzas de dos personas. Un error en uno no expone el otro. El plan gratis permite dos
  proyectos.
- Quién ve qué lo decide la base con Row Level Security, no el panel.

### 3. Panel: Next.js en Vercel, repo nuevo

- `E:\dev\01-web-apps\panel-afiliados`. Next.js, como Setup Justo, para no sumar otra
  tecnología. Dependencias con **yarn** (npm falla en la máquina de Nick).
- Login con email y contraseña de Supabase Auth. El panel usa la llave pública (anon):
  no puede leer nada que la base no le permita a ese usuario.
- Pensado primero para el celular.

## Datos

Campos de la API de Shopee verificados por introspección el 2026-10-02
(`ConversionReport`, `ConversionReportOrder`, `ConversionReportOrderItem`, `PageInfo`).

### `cuenta`

| Columna | Tipo | Nota |
|---|---|---|
| `id` | text, PK | `lanny`, `nick` |
| `nombre` | text | Para mostrar |
| `dueno` | uuid, nullable | `auth.users.id` de quien la ve; null hasta que exista el usuario |

### `perfil`

| Columna | Tipo | Nota |
|---|---|---|
| `usuario` | uuid, PK | `auth.users.id` |
| `es_admin` | boolean | true solo para Nick: ve todas las cuentas |

### `venta`

Una fila por producto vendido. Clave: `(cuenta, conversion_id, order_id, item_id, model_id)`.

| Columna | Origen en Shopee |
|---|---|
| `cuenta` | La cuenta que se consultó |
| `conversion_id`, `order_id`, `item_id`, `model_id` | `conversionId`, `orderId`, `itemId`, `modelId` |
| `clic_en`, `compra_en`, `completada_en` | `clickTime`, `purchaseTime`, `completeTime` (timestamptz; `completada_en` null si no se completó) |
| `estado` | `displayItemStatus` (`COMPLETED`, `PENDING`, `CANCELLED`, lo que venga) |
| `producto`, `imagen_url`, `categoria` | `itemName`, `imageUrl`, `categoryLv1Name` |
| `precio`, `cantidad`, `comision` | `itemPrice`, `qty`, `itemTotalCommission` |
| `origen` | `referrer` de la conversión, tal cual (el panel traduce `Shopeevideo-Shopee` a "Shopee Video") |
| `utm_content` | `utmContent`, guardado para etapas futuras (etiquetar links) |
| `vista_en` | Última vez que la sincronización la vio en Shopee |

### `video`

Copia de `videos_producidos` de `grabados.db`. Clave: `(canal, item_id)`.

| Columna | Nota |
|---|---|
| `canal` | `lanny`, `nick`, `setupjusto` |
| `cuenta` | `lanny` para `lanny`; `nick` para `nick` y `setupjusto` |
| `item_id`, `titulo`, `link`, `archivo`, `herramienta`, `comision_pct`, `precio` | Igual que en `grabados.db` |
| `grabado_en`, `publicado_en` | De `ts` y `publicado_ts` |

### `sincronizacion`

| Columna | Nota |
|---|---|
| `id` | bigserial |
| `cuenta` | null para la copia de videos |
| `empezo`, `termino` | timestamptz |
| `ok` | boolean |
| `filas` | Cuántas filas escribió |
| `error` | Texto del error, si hubo |

### Acceso (RLS)

- `cuenta`, `venta`, `video`, `sincronizacion`: un usuario lee una fila si es admin, o si
  la cuenta de la fila tiene `dueno = auth.uid()`. Las filas de `sincronizacion` con
  `cuenta` null (videos) las ven todos los usuarios logueados.
- Nadie escribe desde el panel. Solo la llave de servicio (que salta RLS) escribe.

## Sincronización, paso a paso

Cada corrida, para cada cuenta por separado:

1. Pide a `conversionReport` los últimos 90 días, recorriendo todas las páginas
   (`pageInfo.hasNextPage` + `scrollId`).
2. Hace upsert de cada fila de `venta` por su clave: si ya existía, se actualizan estado,
   comisión, `completada_en` y `vista_en`.
3. Registra el resultado en `sincronizacion`.

Después, una vez:

4. Lee `videos_producidos` entero y hace upsert en `video`.
5. Registra el resultado en `sincronizacion`.

**Por qué se releen los 90 días cada vez:** una venta queda pendiente semanas antes de
completarse o cancelarse. Leer solo lo nuevo perdería esos cambios. Con unas 70 ventas
por mes en total son pocas páginas.

### Errores

- Una cuenta que falla no frena a la otra: se registra con `ok = false` y su error.
- Nunca se borra una venta. Las que salen de la ventana de 90 días quedan con su último
  estado: es el historial que hoy se pierde.
- Sin la URL o la llave de Supabase en el `.env`, el script termina con un mensaje claro
  antes de llamar a Shopee.
- El log del script no imprime claves ni tokens (lección del bot de Telegram, ver
  memoria `bots-24-7-tareas-programadas`).

## Pantallas

Barra de pestañas abajo. Arriba, selector **Lanny · Nick · Todo**, visible solo para el
admin; Lanny entra directo a lo suyo.

1. **Inicio**: comisión completada, pendiente y cancelada del mes, cada una con la
   diferencia contra el mes anterior. Barras de comisión por mes (completada y
   pendiente). Cartel "Actualizado hace X", en rojo si la última sincronización de esa
   cuenta falló.
2. **Ventas**: lista, la más nueva primero, con foto, producto, comisión, estado y origen.
   Filtros por estado, origen y mes.
3. **Origen**: por origen, ventas, comisión y porcentaje que paga (comisión sobre lo
   vendido, sin canceladas).
4. **Videos**: pendientes de publicar (archivo + link, cuenta del selector); y por cada
   video, las ventas de ese mismo producto en esa cuenta. Aparte, el total de ventas que
   Shopee atribuye a Shopee Video en la cuenta.

Las cuentas en reales con formato brasileño (`R$ 1.234,56`), como en el bot.

### Fuera de alcance, a propósito

- Cambiar algo desde el panel. Marcar un video como publicado sigue siendo por el chat:
  hacerlo desde el panel obligaría a escribir desde la nube en la base de la PC.
- Notificaciones. El aviso de una venta puntual va por tarea programada.
- Etapas 2 a 4.

## Pruebas

- **Transformar** (pytest, como el resto del bot): respuestas de Shopee guardadas como
  fixtures. Casos: venta pendiente que en la corrida siguiente viene completada; venta
  cancelada; respuesta de dos páginas; item sin `completeTime`; `referrer` vacío; mapeo
  de `setupjusto` a la cuenta `nick`.
- **Acceso**: con el proyecto real, un usuario de prueba dueño solo de `lanny` consulta
  `venta` y `video` y no recibe ninguna fila de `nick`. Se corre antes de crear el
  usuario de verdad de Lanny.
- **Panel**: typecheck y build sin errores; revisión visual en tamaño de celular.
- **Punta a punta**: una corrida manual del sincronizador y comparar los totales del
  panel con los del script de ventas del 2026-10-02 (Lanny, 30 días: 46 completadas,
  R$109,60).

## Lo que hace Nick (cuentas y claves, no pasan por el chat)

1. Crear el proyecto de Supabase y pegar `SUPABASE_PANEL_URL`,
   `SUPABASE_PANEL_SERVICE_KEY` y `SUPABASE_PANEL_ANON_KEY` en el `.env` del bot.
2. Crear la cuenta de Vercel (si no tiene) y conectarla con GitHub.
3. Pasar el email de Lanny. La invitación de Supabase sale recién con su OK.

## Orden de construcción

1. Esquema y RLS en Supabase (migración SQL versionada en el repo del panel).
2. Sincronizador con sus tests; una corrida manual para ver números reales.
3. Tarea programada cada 4 horas.
4. Panel: login, Inicio, Ventas, Origen, Videos.
5. Publicar en Vercel, crear usuarios, prueba de acceso.

Cada paso deja algo que funciona solo.
