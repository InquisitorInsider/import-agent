"""API + panel web del import-agent.

Gateway de clientes desde la base DBF del sistema antiguo de Ruta80.

API para el WhatsApp bot (runtime):
  GET  /clientes/buscar?celular=51999...   -> cliente + direcciones, o 404
                                              (Authorization: Bearer <token> si
                                               LOOKUP_TOKEN está configurado)
  GET  /health                             -> salud del servicio + conteos

API para el facturador (runtime, mismo token Bearer):
  GET  /facturacion/folio/{numcheque}      -> una venta en estándar SUNAT
  GET  /facturacion/ventas?fecha=hoy       -> todas las ventas del día
  GET  /facturacion/pendientes?fecha=hoy   -> ventas válidas no facturadas
  POST /facturacion/marcar                 -> marcar una venta como ya emitida

Panel de importación (protegido con ADMIN_PASSWORD si se define):
  GET  /                       -> panel web
  GET  /api/settings           -> configuración + estado del índice
  POST /api/source             -> guardar origen DBF (local o SMB)
  POST /api/source/probar      -> probar conexión al origen (sin importar)
  POST /api/globals            -> guardar bot_db_path / lookup_token / encoding
  POST /api/token/generar      -> generar token seguro para el bot (lo guarda)
  GET  /api/token              -> ver el token actual (en claro)
  GET  /api/facturacion        -> config de facturación electrónica
  POST /api/facturacion        -> guardar config de facturación (editable web)
  POST /api/importar           -> importación masiva (DBF -> índice limpio)
  GET  /api/clientes           -> listar/buscar en el índice
  GET  /api/sync/diff          -> comparar índice (DBF) vs clientes del bot
  POST /api/sync/aplicar       -> aplicar correcciones a clientes del bot
"""
from __future__ import annotations

import os
import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse

from fastapi.security import HTTPBasic, HTTPBasicCredentials

from . import botdb, config, dbf, facturacion, settings, store, sync, ui

_FACT_CACHE = os.path.join(config.DATA_DIR, "fact_cache")

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


@app.get("/api/facturacion")
def api_facturacion_get(_: None = Depends(require_admin)) -> dict:
    """Config de facturación electrónica (emisor, series, IGV por fecha, etc.)."""
    return settings.facturacion()


@app.post("/api/facturacion")
def api_facturacion_set(payload: dict, _: None = Depends(require_admin)) -> dict:
    settings.save_facturacion(payload)
    return settings.facturacion()


# ============================================================
#  Facturación electrónica — lectura de ventas en estándar SUNAT
# ============================================================
def _fact_base() -> str:
    return facturacion.resolver_cache(settings.source(), _FACT_CACHE)


def _build_comprobante(numcheque: int) -> dict:
    enc = settings.dbf_encoding()
    base = _fact_base()
    prods = facturacion.cargar_productos(os.path.join(base, "productos.dbf"), enc)
    venta = facturacion.leer_venta(base, numcheque, enc)
    if not venta:
        raise HTTPException(status_code=404, detail="venta (folio) no encontrada")
    comp = facturacion.construir_comprobante(venta, prods, settings.facturacion())
    comp["ya_facturado"] = store.esta_facturada(numcheque)
    return comp


def _hoy_lima() -> date:
    """Fecha de hoy en Perú (UTC-5, sin horario de verano), sin depender del TZ
    del contenedor."""
    return (datetime.now(timezone.utc) - timedelta(hours=5)).date()


def _parse_fecha(fecha: str) -> date:
    f = (fecha or "hoy").strip().lower()
    if f in ("hoy", "today", ""):
        return _hoy_lima()
    try:
        return datetime.strptime(f, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="fecha inválida (use YYYY-MM-DD o 'hoy')")


def _comprobantes_dia(fecha: str) -> dict:
    dia = _parse_fecha(fecha)
    enc = settings.dbf_encoding()
    base = _fact_base()
    prods = facturacion.cargar_productos(os.path.join(base, "productos.dbf"), enc)
    fc = settings.facturacion()
    fact = store.facturadas_set()
    comps = []
    for v in facturacion.leer_ventas_dia(base, dia, enc):
        comp = facturacion.construir_comprobante(v, prods, fc)
        comp["ya_facturado"] = comp["numcheque_pos"] in fact
        comps.append(comp)
    comps.sort(key=lambda x: x["numcheque_pos"])
    return {"fecha": dia.isoformat(), "total": len(comps), "comprobantes": comps}


def _pendientes_dia(fecha: str) -> dict:
    data = _comprobantes_dia(fecha)
    pend = [c for c in data["comprobantes"] if not c["ya_facturado"]]
    return {"fecha": data["fecha"], "total": len(pend),
            "pendientes": [{"numcheque_pos": c["numcheque_pos"], "serie": c["serie"],
                            "tipo_comprobante": c["tipo_comprobante"],
                            "importe_total": c["totales"]["importe_total"],
                            "origen": c["origen"]} for c in pend]}


# ---------- Llamables por el facturador (token Bearer, igual que el bot) ----------
@app.get("/facturacion/folio/{numcheque}")
def fact_folio(numcheque: int, _: None = Depends(require_lookup)) -> dict:
    return _build_comprobante(numcheque)


@app.get("/facturacion/ventas")
def fact_ventas(fecha: str = "hoy", _: None = Depends(require_lookup)) -> dict:
    return _comprobantes_dia(fecha)


@app.get("/facturacion/pendientes")
def fact_pendientes(fecha: str = "hoy", _: None = Depends(require_lookup)) -> dict:
    return _pendientes_dia(fecha)


@app.post("/facturacion/marcar")
def fact_marcar(payload: dict, _: None = Depends(require_lookup)) -> dict:
    """El facturador reporta una venta como ya emitida (anti-duplicidad)."""
    num = payload.get("numcheque")
    if num is None:
        raise HTTPException(status_code=400, detail="falta 'numcheque'")
    return store.marcar_facturada(num, payload.get("tipo", ""), payload.get("serie", ""),
                                  payload.get("correlativo", ""), payload.get("cdr", ""))


# ---------- Para la prueba del panel (protegido por login de admin) ----------
@app.get("/api/facturacion/folio/{numcheque}")
def api_fact_folio(numcheque: int, _: None = Depends(require_admin)) -> dict:
    return _build_comprobante(numcheque)


@app.get("/api/facturacion/ventas")
def api_fact_ventas(fecha: str = "hoy", _: None = Depends(require_admin)) -> dict:
    return _comprobantes_dia(fecha)


@app.post("/api/token/generar")
def api_token_generar(_: None = Depends(require_admin)) -> dict:
    """Genera un token seguro nuevo para el bot, lo guarda y lo devuelve en claro."""
    token = secrets.token_urlsafe(24)
    settings.save_globals({"lookup_token": token})
    return {"token": token}


@app.get("/api/token")
def api_token_ver(_: None = Depends(require_admin)) -> dict:
    """Devuelve el token actual en claro (panel protegido por ADMIN_PASSWORD)."""
    return {"token": settings.lookup_token()}


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


@app.get("/api/clientes/buscar")
def api_clientes_buscar(celular: str, _: None = Depends(require_admin)) -> dict:
    """Igual que /clientes/buscar pero protegido por el login del panel (no por el
    token del bot). Lo usa la pestaña 'Buscar (prueba)' del panel."""
    cel = dbf.normalize_phone(celular)
    if not cel:
        raise HTTPException(status_code=400,
                            detail=f"celular inválido (se esperan {config.PHONE_DIGITS} dígitos)")
    cli = store.buscar_cliente(cel)
    if not cli:
        raise HTTPException(status_code=404, detail="cliente no encontrado")
    return {"encontrado": True, "celular": cel, **cli}


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
