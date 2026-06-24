# Manual de integración — import-agent

Gateway HTTP que publica datos del sistema POS (base DBF de FoxPro) para ser
consumidos por otros servicios: bot de WhatsApp, sistema de facturación
electrónica, paneles web, etc.

---

## Índice

1. [¿Qué hace este servicio?](#1-qué-hace-este-servicio)
2. [Despliegue con Docker](#2-despliegue-con-docker)
3. [Autenticación](#3-autenticación)
4. [Endpoints de runtime — Clientes](#4-endpoints-de-runtime--clientes)
5. [Endpoints de runtime — Facturación](#5-endpoints-de-runtime--facturación)
6. [Flujo completo de integración con un facturador](#6-flujo-completo-de-integración-con-un-facturador)
7. [Estructuras de datos](#7-estructuras-de-datos)
8. [Referencia de variables de entorno](#8-referencia-de-variables-de-entorno)
9. [Gestión de tokens desde el panel](#9-gestión-de-tokens-desde-el-panel)
10. [Errores comunes](#10-errores-comunes)

---

## 1. ¿Qué hace este servicio?

`import-agent` es un puente de **solo lectura** entre una base de datos DBF
(Visual FoxPro / AMC POS) y cualquier servicio moderno. Hace tres cosas:

| Función | Descripción |
|---|---|
| **Índice de clientes** | Lee `clientesdomicilio.dbf` y `direccionesdomicilio.dbf`, construye un índice SQLite normalizado y lo expone por HTTP. |
| **Datos de ventas** | Lee las tablas del POS (`cheques`, `cheqdet`, `chequespagos` y sus versiones `temp*`) y los convierte al formato SUNAT. |
| **Anti-duplicidad** | Registra qué ventas ya fueron facturadas electrónicamente para evitar emitir dos comprobantes para la misma venta. |

Los archivos DBF se leen desde una **carpeta compartida por SMB** (red local)
o desde un **volumen montado** directamente en el contenedor.

---

## 2. Despliegue con Docker

### 2.1 Imagen pública

```
ghcr.io/inquisitorinsider/import-agent:latest
```

### 2.2 docker-compose mínimo (desarrollo)

```yaml
services:
  import-agent:
    image: ghcr.io/inquisitorinsider/import-agent:latest
    container_name: import-agent
    restart: unless-stopped
    ports:
      - "8095:8000"
    environment:
      TZ: "America/Lima"
      ADMIN_PASSWORD: "mi-clave-secreta"
      DBF_SOURCE_TYPE: "smb"
      SMB_HOST: "192.168.1.50"
      SMB_SHARE: "DATOS"
      SMB_USER: ""
      SMB_PASS: ""
    volumes:
      - import-agent-data:/data

volumes:
  import-agent-data:
    name: import-agent-data
```

Panel web disponible en `http://HOST:8095`.  
Swagger/OpenAPI disponible en `http://HOST:8095/docs`.

### 2.3 Integración en la misma red Docker que el bot

```yaml
services:
  import-agent:
    image: ghcr.io/inquisitorinsider/import-agent:latest
    container_name: import-agent
    restart: unless-stopped
    pull_policy: always
    ports:
      - "8095:8000"
    environment:
      TZ: "America/Lima"
      ADMIN_USER: "admin"
      ADMIN_PASSWORD: "CAMBIA-ESTA-CLAVE"
      DBF_SOURCE_TYPE: "smb"
      SMB_HOST: "192.168.1.X"      # IP del PC con el POS
      SMB_SHARE: "DATOS"
      SMB_DOMAIN: "WORKGROUP"
      DBF_ENCODING: "cp1252"
      PHONE_DIGITS: "9"
      COUNTRY_CODE: "51"
      BOT_DB_PATH: "/bot/pedidos.db"
    volumes:
      - import-agent-data:/data
      - whatsapp-bot_db-data:/bot   # SQLite del bot (solo para sincronización)
    networks:
      - pos-net

networks:
  pos-net:
    name: pos-net
    external: true   # red compartida con el bot y otros servicios

volumes:
  import-agent-data:
    name: import-agent-data
  whatsapp-bot_db-data:
    name: whatsapp-bot_db-data
    external: true
```

Con esta configuración, el bot (u otro servicio en la misma red) puede
llamar al agente como `http://import-agent:8000/clientes/buscar?celular=...`
sin necesidad de exponer el puerto hacia el exterior.

### 2.4 Origen local (DBF montado como volumen)

Si los archivos DBF ya están accesibles como carpeta en el host:

```yaml
environment:
  DBF_SOURCE_TYPE: "local"
  DBF_LOCAL_DIR: "/dbf"
volumes:
  - /ruta/en/el/host/datos:/dbf:ro
  - import-agent-data:/data
```

---

## 3. Autenticación

El servicio tiene **dos capas de autenticación independientes**.

### 3.1 Tokens API (Bearer) — para servicios en runtime

Los endpoints de runtime (`/clientes/buscar`, `/facturacion/*`) usan tokens
Bearer. Si no hay ningún token activo configurado, los endpoints quedan
abiertos en la red local (útil solo en desarrollo).

**Comportamiento:**

- Sin tokens activos configurados → sin autenticación (abierto).
- Con al menos un token activo → todos los endpoints de runtime exigen
  `Authorization: Bearer <token>`.

**Cabecera requerida:**

```
Authorization: Bearer eyJhbGciOiJ...
```

**Permisos posibles para un token:**

| Permiso | Acceso |
|---|---|
| `clientes` | `GET /clientes/buscar` |
| `facturacion` | `GET /facturacion/folio/{n}`, `GET /facturacion/ventas`, `GET /facturacion/pendientes`, `POST /facturacion/marcar` |

Un token puede tener uno o ambos permisos.

### 3.2 HTTP Basic — para el panel de administración

El panel web (`/` y todos los endpoints `/api/*`) usa HTTP Basic.

- Si `ADMIN_PASSWORD` está definida en el entorno, actúa como **clave maestra**
  con acceso total.
- Los usuarios adicionales se crean desde el panel web con permisos granulares.
- Si no hay contraseña configurada ni usuarios guardados, el panel es público
  (útil solo en desarrollo).

---

## 4. Endpoints de runtime — Clientes

### `GET /clientes/buscar`

Busca un cliente en el índice por número de celular.

**Parámetros:**

| Parámetro | Tipo | Descripción |
|---|---|---|
| `celular` | query string | Número de celular en cualquier formato. Se normaliza automáticamente (se elimina el prefijo de país, espacios, guiones). |

**Autenticación:** Bearer token con permiso `clientes`.

**Ejemplo de solicitud:**

```bash
curl "http://import-agent:8000/clientes/buscar?celular=51987654321" \
  -H "Authorization: Bearer TU_TOKEN_AQUI"
```

**Respuesta exitosa (200):**

```json
{
  "encontrado": true,
  "celular": "987654321",
  "nombre": "Juan Pérez García",
  "telefono": "987654321",
  "email": "",
  "updated_at": "2026-06-24T10:30:00",
  "direcciones": [
    {
      "calle": "Av. Los Pinos 123",
      "referencia": "Frente al parque",
      "ciudad": "Lima",
      "numero_ext": "",
      "orden": 1
    }
  ]
}
```

**Respuestas de error:**

| Código | Motivo |
|---|---|
| `400` | Celular inválido (no tiene 9 dígitos numéricos). |
| `401` | Token ausente o inválido. |
| `404` | Cliente no encontrado en el índice. |

**Nota:** La búsqueda opera sobre el **índice SQLite local**, no sobre el DBF
en tiempo real. Para que el índice esté actualizado hay que hacer una
importación desde el panel web o automatizarla.

---

### `GET /health`

Salud del servicio. No requiere autenticación.

```bash
curl http://import-agent:8000/health
```

```json
{
  "status": "ok",
  "clientes": 1523,
  "direcciones": 2870,
  "ultima_importacion": {
    "clientes": 1523,
    "direcciones": 2870,
    "direcciones_huerfanas_omitidas": 3,
    "fecha": "2026-06-24T08:00:00"
  }
}
```

---

## 5. Endpoints de runtime — Facturación

Todos requieren Bearer token con permiso `facturacion`.

> **Importante:** Estos endpoints leen los DBF del POS directamente (con caché
> interna de 10 minutos para las tablas cerradas; las tablas `temp*` del turno
> vigente se refrescan en cada llamada). La primera llamada puede tardar unos
> segundos si hay que descargar los archivos por SMB.

---

### `GET /facturacion/folio/{numcheque}`

Devuelve una venta completa (cabecera + detalle + pagos) en formato SUNAT.

```bash
curl "http://import-agent:8000/facturacion/folio/12345" \
  -H "Authorization: Bearer TU_TOKEN_AQUI"
```

Busca primero en el turno vigente (`tempcheques`) y luego en el cerrado
(`cheques`). Devuelve `404` si el folio no existe.

---

### `GET /facturacion/ventas`

Todas las ventas de un día, ya convertidas a formato SUNAT.

```bash
# Ventas de hoy (hora Lima, UTC-5)
curl "http://import-agent:8000/facturacion/ventas" \
  -H "Authorization: Bearer TU_TOKEN_AQUI"

# Ventas de una fecha específica
curl "http://import-agent:8000/facturacion/ventas?fecha=2026-06-20" \
  -H "Authorization: Bearer TU_TOKEN_AQUI"
```

**Parámetros:**

| Parámetro | Valores | Default |
|---|---|---|
| `fecha` | `hoy` / `today` / `YYYY-MM-DD` | `hoy` |

---

### `GET /facturacion/pendientes`

Ventas del día que **aún no han sido marcadas como facturadas**. Devuelve
solo un resumen (sin los ítems) para una integración más liviana.

```bash
curl "http://import-agent:8000/facturacion/pendientes" \
  -H "Authorization: Bearer TU_TOKEN_AQUI"
```

**Respuesta:**

```json
{
  "fecha": "2026-06-24",
  "total": 3,
  "pendientes": [
    {
      "numcheque_pos": 12345,
      "serie": "B001",
      "tipo_comprobante": "03",
      "importe_total": 45.50,
      "origen": "cerrado"
    }
  ]
}
```

---

### `POST /facturacion/marcar`

Registra que una venta ya fue facturada electrónicamente. Llámalo **después**
de que tu sistema emita el comprobante con éxito. Evita emitir dos veces la
misma venta.

```bash
curl -X POST "http://import-agent:8000/facturacion/marcar" \
  -H "Authorization: Bearer TU_TOKEN_AQUI" \
  -H "Content-Type: application/json" \
  -d '{
    "numcheque": 12345,
    "tipo": "03",
    "serie": "B001",
    "correlativo": "00001234",
    "cdr": "CDR-OK"
  }'
```

**Body (JSON):**

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `numcheque` | integer | **Sí** | Folio del POS (NUMCHEQUE). |
| `tipo` | string | No | Tipo de comprobante SUNAT (`"01"` factura, `"03"` boleta). |
| `serie` | string | No | Serie del comprobante emitido (`"B001"`, `"F001"`). |
| `correlativo` | string | No | Número correlativo asignado por el facturador. |
| `cdr` | string | No | Estado del CDR devuelto por SUNAT. |

**Respuesta (200):**

```json
{
  "numcheque": 12345,
  "serie": "B001",
  "correlativo": "00001234",
  "fecha": "2026-06-24T15:22:10"
}
```

El campo `ya_facturado: true` aparecerá en las respuestas de `/folio/{n}` y
`/ventas` para ese `numcheque` a partir de este momento.

---

## 6. Flujo completo de integración con un facturador

```
Turno cerrado / vigente en el POS
          │
          ▼
GET /facturacion/pendientes          ← obtener la lista de ventas pendientes
          │
          ▼  (para cada venta)
GET /facturacion/folio/{numcheque}   ← obtener datos completos (SUNAT-ready)
          │
          ▼
[tu facturador electrónico]          ← emitir boleta/factura, obtener correlativo
          │
          ▼ (si la emisión fue exitosa)
POST /facturacion/marcar             ← registrar como facturado
```

### Ejemplo en Python

```python
import requests

BASE = "http://import-agent:8000"
HEADERS = {"Authorization": "Bearer TU_TOKEN_AQUI"}

# 1. Obtener ventas pendientes del día
resp = requests.get(f"{BASE}/facturacion/pendientes", headers=HEADERS)
pendientes = resp.json()["pendientes"]

for venta in pendientes:
    num = venta["numcheque_pos"]

    # 2. Obtener datos completos de la venta
    comp = requests.get(f"{BASE}/facturacion/folio/{num}", headers=HEADERS).json()

    # 3. Emitir comprobante en tu sistema (pseudocódigo)
    resultado = mi_facturador.emitir(comp)

    if resultado["ok"]:
        # 4. Marcar como facturado
        requests.post(f"{BASE}/facturacion/marcar", headers=HEADERS, json={
            "numcheque": num,
            "tipo": comp["tipo_comprobante"],
            "serie": comp["serie"],
            "correlativo": resultado["correlativo"],
            "cdr": resultado["cdr"],
        })
```

### Ejemplo en JavaScript / Node.js

```javascript
const BASE = 'http://import-agent:8000';
const HEADERS = { Authorization: 'Bearer TU_TOKEN_AQUI' };

async function facturarPendientes() {
  const { pendientes } = await fetch(`${BASE}/facturacion/pendientes`, { headers: HEADERS })
    .then(r => r.json());

  for (const { numcheque_pos } of pendientes) {
    const comprobante = await fetch(`${BASE}/facturacion/folio/${numcheque_pos}`, { headers: HEADERS })
      .then(r => r.json());

    // emitir con tu sistema...
    const resultado = await miFacturador.emitir(comprobante);

    if (resultado.ok) {
      await fetch(`${BASE}/facturacion/marcar`, {
        method: 'POST',
        headers: { ...HEADERS, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          numcheque: numcheque_pos,
          tipo: comprobante.tipo_comprobante,
          serie: comprobante.serie,
          correlativo: resultado.correlativo,
          cdr: resultado.cdr,
        }),
      });
    }
  }
}
```

---

## 7. Estructuras de datos

### 7.1 Comprobante completo (`/facturacion/folio/{n}` y `/facturacion/ventas`)

```json
{
  "tipo_comprobante": "03",
  "serie": "B001",
  "correlativo": null,
  "fecha_emision": "2026-06-24",
  "moneda": "PEN",
  "numcheque_pos": 12345,
  "origen": "cerrado",
  "ya_facturado": false,
  "anulado": false,

  "cliente": {
    "tipo_doc": "0",
    "num_doc": "",
    "nombre": "VARIOS"
  },

  "items": [
    {
      "codigo": "PROD001",
      "descripcion": "LOMO SALTADO",
      "cantidad": 2,
      "unidad": "NIU",
      "valor_unitario": 18.52,
      "precio_unitario": 20.00,
      "afectacion_igv": "10",
      "valor_venta": 37.04,
      "igv": 2.96,
      "ipm": 0.93
    }
  ],

  "totales": {
    "gravadas": 37.04,
    "igv": 2.96,
    "ipm": 0.93,
    "importe_total": 40.93,
    "tasa_igv": 8.0,
    "tasa_ipm": 2.5,
    "en_letras": "CUARENTA CON 93/100 SOLES"
  },

  "forma_pago": "Contado",

  "medio_pago_interno": [
    {
      "codigo": "EF",
      "nombre": "Efectivo",
      "importe": 40.93
    }
  ]
}
```

**Campos clave:**

| Campo | Descripción |
|---|---|
| `tipo_comprobante` | `"01"` = factura, `"03"` = boleta (catálogo SUNAT). |
| `serie` | Serie configurada en el panel (ej. `"B001"`, `"F001"`). |
| `correlativo` | Siempre `null`; lo asigna el facturador al emitir. |
| `numcheque_pos` | Folio interno del POS. Usar para llamar a `/facturacion/marcar`. |
| `origen` | `"vigente"` (turno actual) o `"cerrado"` (turno anterior). |
| `ya_facturado` | `true` si ya se llamó a `/facturacion/marcar` para este folio. |
| `totales.en_letras` | Importe en palabras (útil para imprimir el PDF). |

### 7.2 Cliente (`/clientes/buscar`)

```json
{
  "encontrado": true,
  "celular": "987654321",
  "nombre": "Juan Pérez García",
  "telefono": "987654321",
  "email": "",
  "updated_at": "2026-06-24T08:00:00",
  "direcciones": [
    {
      "calle": "Av. Los Pinos 123",
      "referencia": "Frente al parque",
      "ciudad": "Lima",
      "numero_ext": "",
      "orden": 1
    }
  ]
}
```

---

## 8. Referencia de variables de entorno

Todas son opcionales salvo las indicadas. La configuración persiste en
`/data/settings.json` y se puede editar desde el panel web sin reiniciar.

| Variable | Default | Descripción |
|---|---|---|
| `ADMIN_USER` | `admin` | Usuario de la clave maestra del panel. |
| `ADMIN_PASSWORD` | _(vacío)_ | Clave maestra del panel. Si se deja vacío, el panel es público. |
| `LOOKUP_TOKEN` | _(vacío)_ | Token legacy (una sola app). Usar el panel para tokens multi-app. |
| `DBF_SOURCE_TYPE` | `smb` | Origen de los DBF: `smb` o `local`. |
| `SMB_HOST` | _(vacío)_ | IP o nombre del host con la carpeta compartida. |
| `SMB_SHARE` | _(vacío)_ | Nombre exacto del recurso compartido. |
| `SMB_PATH` | _(vacío)_ | Subcarpeta dentro del recurso (opcional). |
| `SMB_USER` | _(vacío)_ | Usuario SMB. Vacío si la carpeta es pública. |
| `SMB_PASS` | _(vacío)_ | Contraseña SMB. |
| `SMB_DOMAIN` | `WORKGROUP` | Dominio SMB. |
| `SMB_IP` | _(vacío)_ | IP explícita si el nombre no resuelve por DNS. |
| `DBF_LOCAL_DIR` | _(vacío)_ | Ruta del directorio DBF dentro del contenedor (solo `source_type=local`). |
| `CLIENTES_FILE` | `clientesdomicilio.dbf` | Nombre del archivo de clientes. |
| `DIRECCIONES_FILE` | `direccionesdomicilio.dbf` | Nombre del archivo de direcciones. |
| `DBF_ENCODING` | `cp1252` | Codificación de los DBF (FoxPro Windows ANSI). |
| `PHONE_DIGITS` | `9` | Cantidad de dígitos que debe tener un celular válido. |
| `COUNTRY_CODE` | `51` | Prefijo de país a eliminar al normalizar el celular. |
| `BOT_DB_PATH` | _(vacío)_ | Ruta del SQLite del bot (solo para el panel de sincronización). |
| `DATA_DIR` | `/data` | Directorio de datos del agente (índice SQLite + settings). |
| `TZ` | _(sistema)_ | Zona horaria. Usar `America/Lima` para que "hoy" calcule en hora peruana. |

---

## 9. Gestión de tokens desde el panel

Para crear o administrar tokens API sin reiniciar el contenedor:

1. Abre el panel en `http://HOST:8095` e inicia sesión.
2. Ve a la sección **Tokens API**.
3. Crea un token, asigna un nombre descriptivo y selecciona los permisos
   (`clientes`, `facturacion`, o ambos).
4. Copia el token completo en ese momento — se muestra **solo una vez**.
5. Úsalo en el encabezado `Authorization: Bearer <token>` de tu servicio.

Para rotar un token sin interrumpir el servicio:
- Crea un token nuevo con los mismos permisos.
- Actualiza el secreto en tu servicio.
- Elimina el token anterior.

---

## 10. Errores comunes

| Error | Causa | Solución |
|---|---|---|
| `401 Token inválido o ausente` | Hay tokens activos y no se envió el correcto. | Verificar que el encabezado sea `Authorization: Bearer TOKEN` (sin comillas). |
| `400 celular inválido` | El número enviado no tiene el número de dígitos configurado. | Verificar `PHONE_DIGITS` y el formato del celular. |
| `404 cliente no encontrado` | El celular existe en el POS pero no se ha importado aún. | Hacer una importación desde el panel → **Importar**. |
| `404 venta (folio) no encontrada` | El `numcheque` no existe en ninguna tabla del POS. | Verificar el número de folio directamente en el POS. |
| `400` al consultar `/facturacion/*` | Los DBF no son accesibles (SMB caído, ruta incorrecta). | Verificar con **Probar conexión** en el panel → Configuración. |
| Panel web pide contraseña en loop | Credenciales incorrectas. | Revisar `ADMIN_USER` / `ADMIN_PASSWORD` en el entorno, o usar un usuario creado desde el panel. |

---

*Generado el 2026-06-24 — import-agent v1.0.0*
