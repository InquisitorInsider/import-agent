"""Configuración base del import-agent.

El agente es un GATEWAY de clientes: lee la base DBF del sistema antiguo
(solo lectura), mantiene un índice limpio propio y expone por HTTP lo que el
WhatsApp bot necesita para autocompletar nombres y direcciones.

Igual que print-agent, estos valores de entorno son solo la SEMILLA de la
primera ejecución. Una vez que guardas desde la interfaz web, manda
/data/settings.json.
"""
import os


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


# --- Servidor HTTP ---
HOST = _get("HOST", "0.0.0.0")
PORT = _get_int("PORT", 8000)

# --- Almacenamiento (índice limpio + settings + caché de DBF) ---
DATA_DIR = _get("DATA_DIR", "/data")

# --- Protección de la interfaz web (opcional) ---
ADMIN_USER = _get("ADMIN_USER", "admin")
ADMIN_PASSWORD = _get("ADMIN_PASSWORD")          # si se define, la web pide usuario/clave

# --- Token para que el bot consulte /clientes/buscar (opcional) ---
# Si se define, el endpoint de búsqueda exige Authorization: Bearer <token>.
LOOKUP_TOKEN = _get("LOOKUP_TOKEN")

# --- Codificación de los DBF (FoxPro suele ser Windows ANSI = cp1252) ---
DBF_ENCODING = _get("DBF_ENCODING", "cp1252")

# --- Validación de teléfonos (idcliente) ---
# Regla de Alex: aceptar solo idcliente de N dígitos exactos, numéricos.
PHONE_DIGITS = _get_int("PHONE_DIGITS", 9)
# Prefijo de país a quitar del celular_real del bot al cruzar (Perú = 51).
COUNTRY_CODE = _get("COUNTRY_CODE", "51")

# --- Origen de los DBF (semilla) ---
# source_type: "local" (carpeta montada / volumen) o "smb" (recurso compartido).
SEED_SOURCE = {
    "source_type": _get("DBF_SOURCE_TYPE", "smb").lower(),
    # --- LOCAL: ruta dentro del contenedor donde están (o se montan) los DBF ---
    "local_dir": _get("DBF_LOCAL_DIR", ""),
    # --- SMB: recurso compartido de red ---
    "smb_host": _get("SMB_HOST"),
    "smb_share": _get("SMB_SHARE"),
    "smb_path": _get("SMB_PATH", ""),            # subcarpeta dentro del recurso
    "smb_user": _get("SMB_USER"),
    "smb_pass": _get("SMB_PASS"),
    "smb_domain": _get("SMB_DOMAIN", "WORKGROUP"),
    "smb_ip": _get("SMB_IP"),
    # --- Nombres de archivo de las tablas ---
    "clientes_file": _get("CLIENTES_FILE", "clientesdomicilio.dbf"),
    "direcciones_file": _get("DIRECCIONES_FILE", "direccionesdomicilio.dbf"),
}

# --- Conexión a la BD del bot (para el panel de sincronización) ---
# Ruta al SQLite del WhatsApp bot, montado en el contenedor (solo se usa en el
# panel de sincronización; la búsqueda en runtime NO lo necesita).
SEED_BOT_DB = _get("BOT_DB_PATH", "")
