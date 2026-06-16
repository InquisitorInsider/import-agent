# Subir import-agent a GitHub (público) y desplegarlo en OMV (paso a paso)

Objetivo: dejar el proyecto en GitHub para que **GitHub construya la imagen solo**
(amd64 + **ARM** para la Raspberry Pi) y la publique en GHCR. Luego, en tu OMV,
desplegar es solo pegar un compose corto y pulsar **Up** — sin compilar en el
servidor.

Orden:

1. Crear el repositorio **público** y subir el proyecto.
2. Esperar a que la imagen se construya y dejarla pública.
3. Desplegar en OMV con la imagen.

> Ya tienes cuenta de GitHub (`InquisitorInsider`, la de print-agent y
> whatsapp-bot). Si necesitas crear una desde cero, mira la Parte 1 de la
> `GUIA-GITHUB.md` de print-agent.

---

## Parte 1 · Crear el repositorio y subir el proyecto

El proyecto **ya está inicializado como repositorio git y con su primer commit**.
Tienes dos caminos; elige uno.

### Opción A — Por terminal (recomendada, la más rápida)

Necesitas `git` instalado y, si usas la opción `gh`, la CLI de GitHub.

```bash
cd "ruta/al/proyecto/import-agent"

# Con GitHub CLI (gh): crea el repo público y sube en un solo paso
gh repo create InquisitorInsider/import-agent --public --source=. --remote=origin --push

# --- O bien, a mano ---
# 1) Crea en github.com un repo VACÍO llamado import-agent (Public, sin README).
# 2) Luego:
git branch -M main
git remote add origin https://github.com/InquisitorInsider/import-agent.git
git push -u origin main
```

### Opción B — Por la web (arrastrar archivos)

1. En GitHub, **+ → New repository**.
   - **Repository name:** `import-agent`
   - **Description:** `Gateway de clientes DBF -> WhatsApp bot`
   - Marca **Public**. **No** marques "Add a README".
   - **Create repository**.
2. En la página nueva, **Add file → Upload files**.
3. Abre la carpeta `import-agent/` de tu PC, selecciona **todo el contenido** y
   arrástralo. GitHub respeta las subcarpetas (`app/`).
   - Sube también **`.env.example`**, pero **NUNCA** un `.env` con claves reales.
4. **Commit changes**.

> **Ojo con la carpeta oculta `.github`** (la que construye la imagen sola). Si al
> arrastrar no se subió: **Add file → Create new file** y en el nombre escribe
> exactamente `.github/workflows/docker-publish.yml`, pega el contenido del
> archivo del proyecto y **Commit changes**. Verifica que esté presente.

---

## Parte 2 · Construir la imagen y dejarla pública

### 2.1 Ver la construcción

1. En el repo, abre la pestaña **Actions**.
2. Verás **"Construir y publicar imagen Docker"** corriendo (círculo amarillo).
   Espera 3–6 min hasta que quede en **verde** ✓ (construye amd64 + arm64, por eso
   tarda un poco más).
   - Si sale en rojo, ábrelo, copia el error y me lo pasas.

### 2.2 Hacer pública la imagen (una sola vez)

Por defecto la imagen queda **privada**. Para que el OMV la baje sin login:

1. Tu perfil: **https://github.com/InquisitorInsider** → pestaña **Packages**.
2. Abre el paquete **import-agent**.
3. **Package settings** (a la derecha).
4. **Danger Zone → Change visibility → Public** → confirma escribiendo el nombre.

Tu imagen queda en: `ghcr.io/inquisitorinsider/import-agent:latest`

---

## Parte 3 · Desplegar en OMV

No necesitas subir `app/` ni `Dockerfile` al servidor: solo el compose.

1. En tu PC abre **`docker-compose.omv.yml`** del proyecto y rellena los valores
   marcados con `<<<`:
   - `ADMIN_PASSWORD` — clave del panel.
   - `LOOKUP_TOKEN` — opcional; token que el bot usará para consultar.
   - **Origen DBF** (SMB): `SMB_HOST` (IP del PC con el sistema antiguo),
     `SMB_SHARE` (recurso compartido), `SMB_PATH` (subcarpeta si aplica),
     `SMB_USER`/`SMB_PASS` (vacíos si la comparte es abierta).
   Copia el texto ya editado.
2. En OMV: **Services → Compose → Files → Add (+)**.
   - **Name:** `import-agent`
   - Pega el compose editado. **Save**.
3. Selecciona `import-agent` y pulsa **Up** (▲). OMV **descarga** la imagen de
   GHCR y la levanta (sin compilar).
4. Comprueba: `http://IP_DEL_OMV:8094/health` y abre el panel en
   `http://IP_DEL_OMV:8094`.
5. En el panel: pestaña **Importaciones → Guardar origen → Importación masiva**.

### Detalles de este compose (ya vienen resueltos)

- **Puerto `8094:8000`**: el 8000 ya está ocupado en tu OMV (igual que con
  print-agent). Acceso por `http://IP_OMV:8094`.
- **Red `pos-net`** (la misma de print-agent/bot): el bot podrá llamarlo por
  `http://import-agent:8000`.
- **Monta el volumen `whatsapp-bot_db-data` en `/bot`** con `BOT_DB_PATH=/bot/pedidos.db`,
  para que el **panel de sincronización** pueda comparar y corregir nombres del
  bot. (Si solo quieres comparar sin escribir, añade `:ro` al final del montaje.)

---

## Cómo actualizar en el futuro

1. Cambias el código y haces `git push` (o subes los archivos por la web).
2. GitHub reconstruye la imagen solo (**Actions** → verde).
3. En OMV: **Services → Compose** → `import-agent` → **Pull** (baja la nueva
   imagen) → **Up**.

Tu índice y tu configuración (`/data`) se conservan en cada actualización.

---

## Notas de seguridad

- El repo es público: cualquiera puede ver el **código** (está bien, no hay
  secretos en él ni datos de clientes; los datos viven solo en el DBF y en el
  volumen `/data` del servidor).
- **Nunca** subas un `.env` con claves reales. El `.gitignore` ya lo evita.
- `ADMIN_PASSWORD`, `LOOKUP_TOKEN` y las credenciales SMB viven solo en el
  compose/entorno de tu servidor, no en GitHub.
- El agente abre los DBF en **solo lectura**: no puede dañar el sistema antiguo.
