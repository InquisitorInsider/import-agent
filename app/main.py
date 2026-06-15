"""API + panel web del import-agent.

Gateway de clientes desde la base DBF del sistema antiguo de Ruta80.

API para el WhatsApp bot (runtime):
  GET  /clientes/buscar?celular=51999...   -> cliente + direcciones, o 404
                                              (Authorization: Bearer <token> si
                                               LOOKUP_TOKEN está configurado)
  GET  /health                             -> salud del servicio + conteos

Panel de importación (protegido con ADMIN_PASSWORD si se define):
  GET  /                       -> panel web
  GET  /api/settings           -> configuración + estado del índice
  POST /api/source             -> guardar origen DBF (local o SMB)
  POST /api/source/probar      -> probar conexión al origen (sin importar)
  POST /api/globals            -> guardar bot_db_path / lookup_token / encoding
  POST /api/importar           -> importación masiva (DBF -> índice limpio)
  GET  /api/clientes           -> listar/buscar en el índice
  GET  /api/sync/diff          -> comparar índice (DBF) vs clientes del bot
  POST /api/sync/aplicar       -> aplicar correcciones a clientes del bot
"""
from __future__ import annotations

import secrets

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse

from fastapi.security import HTTPBasic, HTTPBasicCredentials

from . import botdb, config, dbf, settings, store, sync, ui

app = FastAPI(title="import-agent", version="1.0.0", docs_url="/docs")
_basic = HTTPBasic(auto_error=False)


# ---------- Auth de administración (panel / API de config) ----------
def require_admin(creds: HTTPBasicCredentials | None = Depends(_basic)) -> None:
    if not config.ADMIN_PASSWORD:
        return
    ok = (
        creds is not None
        and secrets.compare_digest(creds.username, config.ADMIN_USER)
        and secrets.compare_digest(creds.password, config.ADMIN_PASSWORD)
    )
    if not ok:
        raise HTTPException(status_code=401, detail="No autorizado",
                            headers={"WWW-Authenticate": "Basic"})


# ---------- Auth del bot (búsqueda en runtime) ----------
def require_lookup(authorization: str | None = Header(default=None)) -> None:
    token = settings.lookup_token()
    if not token:
        return  # abierto en la red local
    given = ""
    if authorization and authorization.lower().startswith("bearer "):
        given = authorization[7:].strip()
    if not given or not secrets.compare_digest(given, token):
        raise HTTPException(status_code=401, detail="Token inválido o ausente")


# ============================================================
#  API para el WhatsApp bot (runtime)
# ============================================================
@app.get("/clientes/buscar")
def buscar(celular: str = Query(..., description="celular en cualquier formato"),
           _: None = Depends(require_lookup)) -> dict:
    cel = dbf.normalize_phone(celular)
    if not cel:
        raise HTTPException(status_code=400,
                            detail=f"celular inválido (se esperan {config.PHONE_DIGITS} dígitos)")
    cli = store.buscar_cliente(cel)
    if not cli:
        raise HTTPException(status_code=404, detail="cliente no encontrado")
    return {"encontrado": True, "celular": cel, **cli}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", **store.stats()}


# ============================================================
#  Panel de importación
# ============================================================
@app.get("/", response_class=HTMLResponse)
def panel(_: None = Depends(require_admin)) -> str:
    return ui.PAGE


@app.get("/api/settings")
def api_settings(_: None = Depends(require_admin)) -> dict:
    s = settings.public()
    s["index"] = store.stats()
    s["phone_digits"] = config.PHONE_DIGITS
    s["bot_db_disponible"] = botdb.disponible(settings.bot_db_path())
    return s


@app.post("/api/source")
def api_source(payload: dict, _: None = Depends(require_admin)) -> dict:
    settings.save_source(payload)
    return api_settings()


@app.post("/api/globals")
def api_globals(payload: dict, _: None = Depends(require_admin)) -> dict:
    settings.save_globals(payload)
    return api_settings()


@app.post("/api/source/probar")
def api_source_probar(_: None = Depends(require_admin)) -> dict:
    """Prueba la conexión al origen DBF guardado, sin importar nada."""
    try:
        return dbf.probar(settings.source())
    except dbf.DbfError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Error probando la conexión: {e}")


@app.post("/api/importar")
def api_importar(_: None = Depends(require_admin)) -> dict:
    """Importación masiva: lee los DBF y reemplaza el índice limpio."""
    try:
        data = dbf.read_all(settings.source(), settings.dbf_encoding())
    except dbf.DbfError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Error leyendo DBF: {e}")
    resumen = store.reemplazar_todo(data["clientes"], data["direcciones"])
    return {"ok": True, "resumen": resumen, "dbf_stats": data["stats"]}


@app.get("/api/clientes")
def api_clientes(limit: int = 50, offset: int = 0, q: str = "",
                 _: None = Depends(require_admin)) -> dict:
    return store.listar_clientes(limit=min(limit, 200), offset=offset, q=q)


# ---------- Sincronización con el bot ----------
def _bot_path() -> str:
    p = settings.bot_db_path()
    if not botdb.disponible(p):
        raise HTTPException(
            status_code=400,
            detail="No hay BD del bot accesible. Configura 'Ruta BD del bot' y "
                   "monta el SQLite del bot en el contenedor.")
    return p


@app.get("/api/sync/diff")
def api_sync_diff(_: None = Depends(require_admin)) -> dict:
    path = _bot_path()
    idx = store.all_clientes()
    if not idx:
        raise HTTPException(status_code=400,
                            detail="El índice está vacío. Haz primero una importación masiva.")
    bot = botdb.leer_clientes(path)
    return sync.diff(idx, bot)


@app.post("/api/sync/aplicar")
def api_sync_aplicar(payload: dict, _: None = Depends(require_admin)) -> dict:
    path = _bot_path()
    acciones = payload.get("acciones") or []
    if not acciones:
        raise HTTPException(status_code=400, detail="No hay acciones que aplicar")
    idx = store.all_clientes()
    return sync.aplicar(path, idx, acciones)


@app.on_event("startup")
def _startup() -> None:
    settings.load()
    store.init()
