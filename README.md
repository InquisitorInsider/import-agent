# import-agent

Gateway de **clientes** desde la base **DBF** del sistema antiguo de Ruta80.

Lee `clientesdomicilio.dbf` y `direccionesdomicilio.dbf` en **solo lectura**,
mantiene un **índice limpio** propio (SQLite) y lo expone por HTTP para que el
WhatsApp bot pueda autocompletar el nombre y la dirección reales de un cliente
en vez de aceptar basura como *"un cuarto de pollo"*.

Mismo patrón que `print-agent`: microservicio independiente, en Docker,
consumido por HTTP. Nunca escribe en los DBF.

---

## Qué hace

1. **Importación masiva (DBF → índice limpio).** Lee las dos tablas, valida y
   normaliza, y reemplaza el índice. Re-ejecutar = mantener sincronizado.
2. **Búsqueda en runtime (para el bot).** `GET /clientes/buscar?celular=…`
   devuelve nombre + direcciones si el número existe.
3. **Sincronizar con el bot.** Compara el índice (DBF) contra los clientes que
   ya existen en el bot (cruce por `celular_real`), marca los nombres mal
   escritos en el bot y permite corregirlos con el dato del DBF.

El **panel de importación** (web) es **modular**: hoy gestiona clientes, y está
preparado para sumar más módulos (productos, histórico de pedidos, etc.) como
nuevas tarjetas que reutilizan el mismo origen DBF.

---

## Reglas de los datos (definidas por Alex)

- **`IDCLIENTE` = el celular.** Solo se acepta si tiene **exactamente 9 dígitos
  numéricos**; cualquier otra cosa se omite. Misma regla en la tabla de
  direcciones (la relación cliente↔dirección es por ese campo).
- Campo clave de clientes: **`NOMBRE`**. Si está vacío, el cliente se omite (el
  objetivo es justamente conseguir el nombre real). `TELEFONO1` debería coincidir
  con `IDCLIENTE` (se reporta cuántos no coinciden).
- Campo clave de direcciones: **`CALLE`**. También se importa **`REFERENCIA`**
  cuando trae dato.
- Codificación **cp1252** (FoxPro Windows ANSI) → acentos y ñ correctos
  (`BREÑA`, `PEÑA`).

Con tus tablas de muestra: **4.938 clientes** válidos con nombre y **2.745
direcciones** importadas (se omiten ~363 idcliente inválidos, ~732 sin nombre y
las direcciones huérfanas).

---

## Endpoints

### Para el bot (runtime)
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/clientes/buscar?celular=…` | Cliente + direcciones, o 404. Acepta `999…`, `51999…`, `…@s.whatsapp.net`. Si `LOOKUP_TOKEN` está definido, exige `Authorization: Bearer`. |
| GET | `/health` | Salud + conteos del índice. |

### Panel (protegido con `ADMIN_PASSWORD`)
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Panel web. |
| POST | `/api/importar` | Importación masiva. |
| GET | `/api/clientes?q=&limit=&offset=` | Listar/buscar en el índice. |
| POST | `/api/source` · `/api/globals` | Guardar origen DBF / conexión bot. |
| GET | `/api/sync/diff` | Diferencias índice (DBF) vs bot. |
| POST | `/api/sync/aplicar` | Aplicar correcciones al bot. |

---

## Despliegue en OMV

Usa `docker-compose.omv.yml` (variables inline). Publica en **`8094:8000`**
(el 8000 ya está ocupado en tu OMV) → `http://IP_OMV:8094`. Se une a la red
`pos-net` para que el bot lo llame por `http://import-agent:8000`.

1. En **Services → Compose → Files → Add (+)**, pega `docker-compose.omv.yml`.
2. Rellena los valores `<<<` (clave del panel, datos SMB de la carpeta con los
   DBF).
3. Para el panel de sincronización, ya monta el volumen `whatsapp-bot_db-data`
   del bot en `/bot` y usa `BOT_DB_PATH=/bot/pedidos.db`.
4. Levanta el stack y abre el panel. **Configura el origen → Importación masiva.**

Imagen multi-arquitectura (igual que print-agent): el build debe ser
`linux/amd64,linux/arm64` para el Raspberry Pi.

### Local / desarrollo
```bash
cp .env.example .env     # ajusta valores
docker compose up --build
# panel: http://localhost:8000
```
Para probar sin SMB, pon `DBF_SOURCE_TYPE=local`, monta tu carpeta de `.dbf`
en `/dbf` y `DBF_LOCAL_DIR=/dbf`.

---

## Fase 2 — enganche en el WhatsApp bot

Cuando un cliente escribe y **no existe** en la BD del bot, antes de pedirle el
nombre, el bot consulta al import-agent; si lo encuentra, lo crea con el nombre
y la dirección reales **sin preguntar**:

```js
const AGENT = 'http://import-agent:8000';
async function buscarEnImportador(celular){
  try{
    const r = await fetch(AGENT + '/clientes/buscar?celular=' + encodeURIComponent(celular),
      { headers: { Authorization: 'Bearer ' + process.env.IMPORT_TOKEN } });
    if (r.ok) return await r.json();   // { nombre, direcciones:[...] }
  }catch(e){}
  return null;
}
```

La opción **"sincronizar clientes"** dentro del bot puede, además, llamar al
panel/`/api/sync/diff` para revisar y corregir nombres en lote.

> Nota: no se pueden **crear** clientes en el bot desde el agente, porque la PK
> del bot es el **LID de WhatsApp** (existe solo cuando la persona escribe). Por
> eso los altas nuevos entran en runtime, y el panel de sincronización solo
> **actualiza** clientes que ya existen en el bot.
