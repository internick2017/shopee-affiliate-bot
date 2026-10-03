# Panel etapa 2 (videos a fondo) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Marcar videos como publicados desde el panel y ver qué videos rinden (vista Desempenho).

**Architecture:** Una tabla nueva `publicacao` en Supabase, escrita solo por el panel con RLS. `sync_panel.py` trae esas marcas a `grabados.db` antes de subir los videos, así ninguna corrida pisa una marca. El panel calcula el desempeño en un módulo puro (`lib/videos.ts`) y lo muestra en dos vistas de la pestaña Vídeos.

**Tech Stack:** Python 3.12 + requests + pytest (bot); Next.js 16 + React 19 + supabase-js 2 + shadcn/base-ui + recharts + vitest (panel); Postgres/PostgREST de Supabase.

**Spec:** `docs/superpowers/specs/2026-10-02-panel-etapa2-videos-design.md`

**Repos:** bot = `E:\dev\07-tools-personal\shopee-affiliate-bot`; panel = `E:\dev\01-web-apps\panel-afiliados`. Rama `feat/panel-etapa2` en los dos.

## Global Constraints

- Textos de la interfaz en portugués de Brasil; comentarios de código en español, como el resto del código.
- Prosa sin rayas largas ni flechas.
- Commits sin `Co-Authored-By` ni ninguna mención de IA. Push y merge solo con el OK de Nick.
- Panel: `yarn` y binarios `./node_modules/.bin/*` (npm no anda en esta máquina).
- La llave de servicio vive solo en el `.env` del bot; nunca en el panel ni en un mensaje de error o log.
- Una migración a la base real la aplica Nick en el SQL Editor de Supabase (o la aplica el agente solo con su OK explícito).
- Canales de Desempenho y Publicar: solo `lanny` y `nick`. `setupjusto` queda afuera.
- Origen de venta por video: `"Shopeevideo-Shopee"`. Corte de "sin ventas": 14 días.

## Rulings sobre el spec

- **Período:** filtra comisión y cantidad de ventas. "Días hasta la primera venta", "% que vendieron" y "sin ventas" usan todo el historial: son propiedades del video, y con el período un video que vendió hace 40 días figuraría como "nunca vendió" en 30 días.
- **Sincronización:** `sincronizar` no cambia de forma. `traer_marcas(db, store)` corre antes en `main()`, y su error entra en `sincronizar(..., error_marcas=...)` para marcar la corrida de videos como fallida.
- **Marcas repetidas:** el panel inserta con `upsert(..., { ignoreDuplicates: true })` (ON CONFLICT DO NOTHING). Si PostgREST exige permiso de update para eso, la Task 2 lo detecta y se pasa a insertar de a una ignorando el error 23505.

## Review Focus

1. Video marcado en el panel y también confirmado en la PC: se muestra una vez, con la fecha de la PC, sin "Desfazer". (Task 4, `estadoDosVideos`)
2. `publicado_en` llega de PostgREST como `...+00:00`; con `Z` también tiene que parsear. (Task 1, `traer_marcas`)
3. Marcar varios cuando otro ya marcó alguno: no falla el lote. (Task 2, verificación real)
4. Vista "Tudo" del admin: Publicar no muestra `setupjusto` ni publicados. (Task 4, `paraPublicar`)
5. Ventas con precio 0, o video sin `comision_pct`: tasa real `null`, nunca `NaN` ni `Infinity`. (Task 4, `desempenhoPorVideo`)

---

### Task 1: Bot, traer las marcas del panel

**Files:**
- Modify: `src/grabados_store.py` (clase `VideosStore`)
- Modify: `src/panel_sync.py` (`Supabase`, `sincronizar`, nueva `traer_marcas`)
- Modify: `sync_panel.py` (`main`)
- Test: `tests/test_videos_store.py`, `tests/test_panel_sync.py`

**Interfaces:**
- Produces:
  - `VideosStore.marcar_si_falta(item_id: int, canal: str, *, cuando: float) -> bool`: pone `publicado_ts` solo si es NULL; True si cambió.
  - `Supabase.leer(tabla: str, columnas: str) -> list[dict]`: GET `/rest/v1/{tabla}?select={columnas}`; status >= 300 lanza `RuntimeError` con el mismo formato que `_post` (sin la llave).
  - `traer_marcas(db, store) -> tuple[int, str | None]`: (cuántas marcó, error o None). Videos que no existen en `store` se loguean con `logger.warning` y no son error.
  - `sincronizar(..., error_marcas: str | None = None)`: si viene, la corrida de videos se registra `ok=False` con ese texto unido al aviso de canales (`"; "`).

- [ ] **Step 1: Tests de `marcar_si_falta`** en `tests/test_videos_store.py`:
  `test_marcar_si_falta_marca_uno_sin_publicar` (True y `publicado_ts == cuando`), `test_marcar_si_falta_no_pisa_uno_publicado` (False y conserva la fecha vieja), `test_marcar_si_falta_inexistente` (False).
- [ ] **Step 2: Tests de `Supabase.leer` y `traer_marcas`** en `tests/test_panel_sync.py`. Sumar `get(url, *, headers, timeout)` a `_FakeHttp` y `leer`/`marcas` a `_FakeSupabase` (con `falla_en="publicacao"` lanza). Tests:
  - `test_leer_hace_get_con_select` (URL termina en `/rest/v1/publicacao?select=canal,item_id,publicado_en`; header apikey).
  - `test_leer_error_no_incluye_la_llave`.
  - `test_traer_marcas_marca_sin_publicar` con un `VideosStore` real en `tmp_path`: fila `{"canal": "lanny", "item_id": 7, "publicado_en": "2026-10-02T12:00:00+00:00"}` deja `publicado_ts == datetime(2026,10,2,12,tzinfo=UTC).timestamp()`, devuelve `(1, None)`.
  - `test_traer_marcas_acepta_fecha_con_Z` (`"2026-10-02T12:00:00Z"`).
  - `test_traer_marcas_no_pisa_publicado` (devuelve `(0, None)`, fecha intacta).
  - `test_traer_marcas_video_desconocido_se_saltea` (`(0, None)`, no lanza).
  - `test_traer_marcas_si_supabase_falla_devuelve_error` (`(0, "supabase caido")` o que contenga ese texto).
  - `test_error_de_marcas_marca_la_corrida_de_videos`: `sincronizar({}, [_video()], db, ahora=_T, pausa=0, error_marcas="x")` sube el video igual (`db.upserts[0][0] == "video"`), `r["videos"] is False`, `"x" in db.registros[0]["error"]`.
- [ ] **Step 3: Correr y ver que fallan.** `python -m pytest tests/test_videos_store.py tests/test_panel_sync.py -q`. Expected: FAIL por atributos inexistentes.
- [ ] **Step 4: Implementar** `marcar_si_falta` (UPDATE ... WHERE publicado_ts IS NULL), `Supabase.leer`, `traer_marcas` (usa `store.ya_tiene_video` para distinguir desconocido; `datetime.fromisoformat(...).timestamp()`), el kwarg `error_marcas` en `sincronizar`, y en `main()`: crear el `VideosStore`, llamar `traer_marcas`, loguear cuántas marcó, después `listar` y `sincronizar(..., error_marcas=error)`.
- [ ] **Step 5: Correr la suite entera.** `python -m pytest -q`. Expected: todo verde (510 + los nuevos).
- [ ] **Step 6: Commit** en el bot: `feat(panel): traer las marcas de publicado del panel antes de subir los videos`.

### Task 2: Base, tabla `publicacao` con RLS y verificación real

**Files:**
- Create: `E:\dev\01-web-apps\panel-afiliados\supabase\migrations\0002_publicacao.sql`
- Modify: `scripts/verificar_acceso_panel.py` (bot)

**Interfaces:**
- Produces: tabla `publicacao(canal text, item_id bigint, publicado_en timestamptz default now(), marcado_por uuid default auth.uid())`, PK `(canal, item_id)`, FK a `video(canal, item_id)`.

- [ ] **Step 1: Escribir la migración.** Tabla del spec; `grant select, insert, delete on publicacao to authenticated`; `grant all ... to service_role`; RLS activada; tres políticas, con `v` = la fila de `video` del mismo `(canal, item_id)`:
  - `leer_publicacao` (select): existe `v` y `(es_admin() or v.cuenta in (select mis_cuentas()))`.
  - `crear_publicacao` (insert, with check): lo mismo y `marcado_por = auth.uid()`.
  - `borrar_publicacao` (delete): lo mismo y `v.publicado_en is null`.
  Al final, `revoke all on cuenta, perfil, venta, video, sincronizacion, publicacao from anon;`.
- [ ] **Step 2: Ampliar el script** de verificación (antes de aplicar, así falla). Crea además la cuenta `prueba2` (sin dueño), un video `(canal "prueba", item 1, cuenta "prueba")`, otro `(canal "prueba", item 2, cuenta "prueba", publicado_en ya puesto)` y uno `(canal "prueba2", item 3, cuenta "prueba2")`. Casos nuevos, con el token del usuario y la llave anon:
  - marca su video 1 con `Prefer: resolution=ignore-duplicates` y `on_conflict=canal,item_id`: status < 300;
  - la misma marca otra vez: status < 300 y sigue habiendo una sola fila;
  - marca el video 3 (ajeno): rechazado (status >= 400);
  - con la llave de servicio se crea la marca del video 2; el usuario la borra: la fila sigue (leída con servicio);
  - con servicio se crea la marca del video 3; el usuario la borra: la fila sigue;
  - el usuario borra su marca del video 1 (no confirmado): la fila ya no está;
  - sin sesión (Bearer anon), marcar el video 1: rechazado.
  El `finally` borra en orden: `publicacao`, `video`, `venta`, `cuenta` (prueba y prueba2), usuario. El chequeo final cuenta los resultados esperados, no un 5 fijo.
- [ ] **Step 3: Correr el script sin migración.** `python scripts/verificar_acceso_panel.py`. Expected: FAIL en los casos nuevos (la tabla no existe), "limpieza ok".
- [ ] **Step 4: Aplicar la migración en la base real.** Pedirle a Nick que la pegue en el SQL Editor (o aplicarla con su OK).
- [ ] **Step 5: Correr el script de nuevo.** Expected: todos PASS, "limpieza ok". Si "marca repetida" falla por permiso de update, aplicar el ruling de marcas repetidas y anotarlo.
- [ ] **Step 6: Commits:** panel `feat(base): tabla publicacao para marcar videos desde el panel`; bot `test(panel): verificar contra la base real quien puede marcar videos`.

### Task 3: Panel, leer y escribir marcas

**Files:**
- Modify: `lib/tipos.ts`, `lib/datos.ts`, `app/(panel)/contexto.tsx`, `app/(panel)/layout.tsx`

**Interfaces:**
- Consumes: tabla `publicacao` (Task 2).
- Produces:
  - `type Publicacao = { canal: string; item_id: number; publicado_en: string }`; `Video` suma `comision_pct: number | null; precio: number | null`.
  - `datos.publicacoes(): Promise<Publicacao[]>` (la RLS filtra).
  - `datos.marcarPublicados(videos: { canal: string; item_id: number }[]): Promise<void>` (upsert ignoreDuplicates, `onConflict: "canal,item_id"`).
  - `datos.desmarcar(v: { canal: string; item_id: number }): Promise<void>`.
  - `Datos` suma `publicacoes: Publicacao[]`; el contexto suma `recarregarPublicacoes: () => Promise<void>`.

- [ ] **Step 1: Implementar** los tipos, las tres funciones de `datos.ts` (lanzan `Error(error.message)` como las demás) y la carga de `publicacoes` junto con ventas y videos en el layout. `recarregarPublicacoes` vuelve a leer solo `publicacoes` y actualiza `cargados`.
- [ ] **Step 2: Verificar.** `./node_modules/.bin/tsc --noEmit` y `./node_modules/.bin/vitest run`. Expected: sin errores, tests existentes verdes.
- [ ] **Step 3: Commit:** `feat(panel): leer y escribir marcas de publicado`.

### Task 4: Panel, cuentas de videos (`lib/videos.ts`)

**Files:**
- Create: `lib/videos.ts`, `lib/videos.test.ts`

**Interfaces:**
- Consumes: `Video`, `Venta`, `Publicacao` (Task 3); `noPeriodo`, `Periodo` de `lib/periodo.ts`.
- Produces:
  - `type VideoComEstado = Video & { publicadoEn: string | null; confirmado: boolean }`.
  - `estadoDosVideos(videos: Video[], publicacoes: Publicacao[]): VideoComEstado[]`: `publicadoEn = video.publicado_en ?? publicacao?.publicado_en ?? null`; `confirmado = video.publicado_en != null`.
  - `paraPublicar(videos: VideoComEstado[]): VideoComEstado[]`: canales `lanny`/`nick`, `publicadoEn == null`.
  - `publicadosRecentemente(videos: VideoComEstado[], agora: Date, dias = 7): VideoComEstado[]`.
  - `ferramenta(h: string | null): "Flow" | "Flow Music" | "Outra"`.
  - `type Desempenho = { canal; item_id; cuenta; titulo; ferramenta; publicadoEn; comissao: number; vendasVideo: number; vendasOutras: number; vendeuAlgumaVez: boolean; diasAtePrimeira: number | null; prometidoPct: number | null; realPct: number | null }`.
  - `desempenhoPorVideo(videos: VideoComEstado[], ventas: Venta[], periodo: Periodo, agora: Date): Desempenho[]`, ordenado por comisión desc.
  - `resumoDesempenho(linhas: Desempenho[]): { publicados: number; pctComVenda: number; comissao: number; medianaDias: number | null }`.
  - `agrupar(linhas: Desempenho[], chave: "ferramenta" | "canal"): { grupo: string; videos: number; pctComVenda: number; comissaoMedia: number }[]`.
  - `semVendas(linhas: Desempenho[], agora: Date, dias = 14): Desempenho[]`.

- [ ] **Step 1: Tests** en `lib/videos.test.ts` (`AGORA = 2026-10-02T15:00:00Z`; helpers `venta()` y `video()` como en `periodo.test.ts`):
  - `estadoDosVideos`: con solo publicacao, `publicadoEn` de la marca y `confirmado false`; con las dos, fecha del video y `confirmado true`.
  - `paraPublicar`: excluye `setupjusto` y los publicados (incluidos los marcados solo en el panel).
  - `ferramenta`: `"Flow Music"` es Flow Music; `"Flow (I2V desde imagen validada)"` y `"Flow"` son Flow; `null` es Outra.
  - venta por Shopee Video anterior a la publicación no cuenta; posterior sí (`vendasVideo`, `comissao`).
  - video sin publicación cuenta ventas desde `grabado_en`, y `diasAtePrimeira` es `null`.
  - venta por WhatsApp va a `vendasOutras`; cancelada no cuenta en nada.
  - `diasAtePrimeira`: publicado 2026-09-01T12Z, primera venta 2026-09-04T12Z: `3`.
  - período `30d` excluye de `comissao` una venta de agosto, pero `vendeuAlgumaVez` sigue `true`.
  - `realPct`: comisión 5 sobre precio 50 x 2: `5`; `prometidoPct` = `comision_pct`; con ventas de precio 0, `realPct` es `null`; sin `comision_pct`, `prometidoPct` es `null`.
  - `resumoDesempenho`: mediana de `[1, 3, 10]` es `3`; de `[]` es `null`; `pctComVenda` cuenta solo publicados.
  - `agrupar("ferramenta")`: un grupo por herramienta con `pctComVenda` y `comissaoMedia` correctos.
  - `semVendas`: publicado hace 20 días sin ventas entra; hace 10 no; sin publicación no; que vendió alguna vez no.
- [ ] **Step 2: Correr y ver que fallan.** `./node_modules/.bin/vitest run lib/videos.test.ts`. Expected: FAIL (módulo inexistente).
- [ ] **Step 3: Implementar** `lib/videos.ts`. Días = `Math.floor(ms / 86_400_000)`.
- [ ] **Step 4: Correr toda la suite.** `./node_modules/.bin/vitest run`. Expected: verde.
- [ ] **Step 5: Commit:** `feat(panel): cuentas de desempeno de videos`.

### Task 5: Panel, vista Publicar

**Files:**
- Create: `components/painel/segmentado.tsx`, `components/painel/videos/publicar.tsx`
- Modify: `app/(panel)/videos/page.tsx`, `app/(panel)/layout.tsx` (el selector de cuenta pasa a usar `Segmentado`)

**Interfaces:**
- Consumes: `estadoDosVideos`, `paraPublicar`, `publicadosRecentemente` (Task 4); `marcarPublicados`, `desmarcar`, `recarregarPublicacoes` (Task 3).
- Produces: `Segmentado<T extends string>({ opcoes: { valor: T; texto: string }[]; valor: T; mudar: (v: T) => void; rotulo: string })`, el mismo estilo de pastillas del encabezado.

- [ ] **Step 1: `Segmentado`** extraído del selector de cuenta del layout, y el layout lo usa (sin cambio visual).
- [ ] **Step 2: Página Vídeos** con `Segmentado` "Publicar" / "Desempenho" (por defecto Publicar) que muestra `<Publicar/>` o `<Desempenho/>` (este último puede ser un placeholder hasta la Task 6).
- [ ] **Step 3: `Publicar`:** lista de `paraPublicar` con producto, archivo, `Badge` del canal, link y botón "Publicado". Al tocar: estado "salvando" en la fila, `marcarPublicados([v])`, `recarregarPublicacoes()`. Una fila marcada solo en el panel (`publicadoEn` y `!confirmado`) muestra "Publicado agora · Desfazer". Error: la fila vuelve y aparece "Não foi possível marcar. Tente de novo." "Selecionar vários": casillas, botón "Marcar N como publicados" con confirmación (`window.confirm` alcanza). Abajo, plegable, "Publicados recentemente" (7 días).
- [ ] **Step 4: Verificar.** `tsc --noEmit`, `vitest run`, `next build`. Expected: verdes.
- [ ] **Step 5: Commit:** `feat(panel): marcar videos como publicados`.

### Task 6: Panel, vista Desempenho

**Files:**
- Create: `components/painel/videos/desempenho.tsx`
- Modify: `app/(panel)/videos/page.tsx`

**Interfaces:**
- Consumes: `desempenhoPorVideo`, `resumoDesempenho`, `agrupar`, `semVendas` (Task 4); `periodo`/`setPeriodo` del contexto; `SeletorPeriodo`, `FotoProduto` no (videos no tienen foto: usar la de una venta del mismo producto si existe, si no, nada).

- [ ] **Step 1: Implementar** con el selector de período arriba y, en orden: 4 tarjetas (publicados, % que venderam, comissão via vídeo, dias até a 1ª venda); "Ranking de vídeos" (10 y botón "Ver todos"); "Flow vs Flow Music" y "Por canal" (tablas chicas o barras, en grilla de dos en la PC); "Prometido vs real" (promedios y los 5 con mayor diferencia); "Sem vendas" (lista). Mismo lenguaje visual que el Início (Card, `Vazio`, `reais`).
- [ ] **Step 2: Verificar.** `tsc --noEmit`, `vitest run`, `next build`. Expected: verdes.
- [ ] **Step 3: A mano en el navegador** (preview `panel-afiliados`, usuario admin temporal creado y borrado con el script del scratchpad): marcar uno, deshacer, marcar varios, ver Desempenho en celular y PC, claro y oscuro. Borrar las marcas de prueba que no correspondan a videos realmente publicados.
- [ ] **Step 4: Commit:** `feat(panel): vista de desempeno de videos`.

### Task 7: Cierre

- [ ] **Step 1:** correr `sync_panel.py` una vez a mano y confirmar en el log que trae marcas y sube videos sin error.
- [ ] **Step 2:** actualizar la memoria `panel-reportes-afiliados.md` (etapa 2 hecha, el panel ya escribe en `publicacao`).
- [ ] **Step 3:** revisión final de las dos ramas y pedirle a Nick el OK para mergear y pushear (el push del panel publica en Vercel).
