"""API + panel web del import-agent.

Gateway de clientes desde la base DBF del sistema antiguo de Ruta80.

API para el WhatsApp bot (runtime):
  GET  /clientes/buscar?celular=51999...   -> cliente + direcciones, o 404
                                              (Authorization: Bearer <token> si
                                               hay tokens configurados)
  GET  /health                             -> salud del servicio + conteos

API para el facturador (runtime, token Bearer con permiso 'facturacion'):
  GET  /facturacion/folio/{numcheque}      -> una venta en estándar SUNAT
  GET  /facturacion/ventas?fecha=hoy       -> todas las ventas del día
  GET  /facturacion/pendientes?fecha=hoy   -> ventas válidas no facturadas
  POST /facturacion/marcar                 -> marcar una venta como ya emitida

Panel de importación (protegido con ADMIN_PASSWORD o usuarios guardados):
  GET  /                       -> panel web
  GET  /api/me                 -> usuario actual + permisos
  GET  /api/settings           -> configuración + estado del índice
  POST /api/source             -> guardar origen DBF  [config]
  POST /api/source/probar      -> probar conexión DBF  [config]
  POST /api/botdb/probar       -> probar BD del bot    [config]
  POST /api/globals            -> guardar globals      [config]
  GET  /api/facturacion        -> config facturación   [factura]
  POST /api/facturacion        -> guardar facturación  [factura]
  POST /api/importar           -> importación masiva   [importar]
  GET  /api/clientes/buscar    -> buscar (prueba)      [buscar]
  GET  /api/clientes           -> listar               [buscar]
  GET  /api/sync/diff          -> comparar índice/bot  [sync]
  POST /api/sync/aplicar       -> aplicar correcciones [sync]

Gestión de tokens API:
  GET    /api/tokens           -> listar tokens        [tokens]
  POST   /api/tokens           -> crear token          [tokens]
  PATCH  /api/tokens/{id}      -> actualizar token     [tokens]
  POST   /api/tokens/{id}/regenerar -> nuevo valor     [tokens]
  DELETE /api/tokens/{id}      -> eliminar token       [tokens]

Gestión de usuarios del panel:
  GET    /api/usuarios         -> listar usuarios      [usuarios]
  POST   /api/usuarios         -> crear usuario        [usuarios]
  PATCH  /api/usuarios/{u}     -> actualizar usuario   [usuarios]
  DELETE /api/usuarios/{u}     -> eliminar usuario     [usuarios]
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from . import botdb, config, dbf, facturacion, settings, store, sync, ui

_FACT_CACHE = os.path.join(config.DATA_DIR, "fact_cache")

app = FastAPI(title="import-agent", version="1.0.0", docs_url="/docs")
_basic = HTTPBasic(auto_error=False)


# ── Auth: panel (HTTP Basic) ───────────────────────────────────────────────────

def require_admin(perm: str | None = None):
    """Devuelve un Depends que autentica al usuario del panel.

    Si 'perm' se indica, el usuario debe tener ese permiso (o '*').
    """
    def _check(creds: HTTPBasicCredentials | None = Depends(_basic)) -> dict:
        no_auth = not config.ADMIN_PASSWORD and not _data_has_users()
        if no_auth:
            return {"username": "anon", "permisos": ["*"]}
        user = None
        if creds:
            user = settings.verify_admin(creds.username, creds.password)
        if not user:
            raise HTTPException(
                status_code=401, detail="No autorizado",
                headers={"WWW-Authenticate": 'Basic realm="import-agent"'})
        if perm and "*" not in user.get("permisos", []) and perm not in user.get("permisos", []):
            raise HTTPException(status_code=403, detail=f"Sin permiso: {perm}")
        return user
    return _check


def _data_has_users() -> bool:
    return bool(settings.admin_users())


# ── Auth: tokens API (Bearer) ─────────────────────────────────────────────────

def require_lookup(perm: str = "clientes"):
    """Devuelve un Depends que valida el Bearer token para endpoints de runtime."""
    def _check(authorization: str | None = Header(default=None)) -> None:
        if not settings.has_any_api_token():
            return  # sin tokens configurados → abierto en la red local
        given = ""
        if authorization and authorization.lower().startswith("bearer "):
            given = authorization[7:].strip()
        if not given or not settings.verify_api_token(given, perm):
            raise HTTPException(status_code=401, detail="Token inválido o ausente")
    return _check


# ══════════════════════════════════════════════════════════════════════════════
#  API runtime — bot
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/clientes/buscar")
def buscar(celular: str = Query(..., description="celular en cualquier formato"),
           _: None = Depends(require_lookup("clientes"))) -> dict:
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


# ══════════════════════════════════════════════════════════════════════════════
#  API runtime — facturador
# ══════════════════════════════════════════════════════════════════════════════

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


@app.get("/facturacion/folio/{numcheque}")
def fact_folio(numcheque: int, _: None = Depends(require_lookup("facturacion"))) -> dict:
    return _build_comprobante(numcheque)


@app.get("/facturacion/ventas")
def fact_ventas(fecha: str = "hoy", _: None = Depends(require_lookup("facturacion"))) -> dict:
    return _comprobantes_dia(fecha)


@app.get("/facturacion/pendientes")
def fact_pendientes(fecha: str = "hoy", _: None = Depends(require_lookup("facturacion"))) -> dict:
    return _pendientes_dia(fecha)


@app.post("/facturacion/marcar")
def fact_marcar(payload: dict, _: None = Depends(require_lookup("facturacion"))) -> dict:
    num = payload.get("numcheque")
    if num is None:
        raise HTTPException(status_code=400, detail="falta 'numcheque'")
    return store.marcar_facturada(num, payload.get("tipo", ""), payload.get("serie", ""),
                                  payload.get("correlativo", ""), payload.get("cdr", ""))


@app.get("/facturacion/productos")
def fact_productos(_: None = Depends(require_lookup("facturacion"))) -> dict:
    """Catálogo de productos.dbf (código, descripción, activo) para que otros
    servicios (ej. horno-ruta80) sincronicen su propio catálogo/equivalencias."""
    enc = settings.dbf_encoding()
    base = _fact_base()
    prods = facturacion.cargar_productos(os.path.join(base, "productos.dbf"), enc)
    items = [
        {"codigo": clave, "descripcion": info.get("desc", ""), "activo": not info.get("nofact")}
        for clave, info in prods.items()
    ]
    items.sort(key=lambda x: x["descripcion"] or x["codigo"])
    return {"total": len(items), "productos": items}


# ══════════════════════════════════════════════════════════════════════════════
#  Panel — general
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
def panel(_: dict = Depends(require_admin())) -> str:
    return ui.PAGE


@app.get("/api/me")
def api_me(user: dict = Depends(require_admin())) -> dict:
    return {"username": user["username"], "permisos": user.get("permisos", [])}


@app.get("/api/settings")
def api_settings(_: dict = Depends(require_admin())) -> dict:
    s = settings.public()
    s["index"] = store.stats()
    s["phone_digits"] = config.PHONE_DIGITS
    s["bot_db_disponible"] = botdb.disponible(settings.bot_db_path())
    return s


# ══════════════════════════════════════════════════════════════════════════════
#  Panel — Configuración  [perm: config]
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/source")
def api_source(payload: dict, _: dict = Depends(require_admin("config"))) -> dict:
    settings.save_source(payload)
    return api_settings(_)


@app.post("/api/globals")
def api_globals(payload: dict, _: dict = Depends(require_admin("config"))) -> dict:
    settings.save_globals(payload)
    return api_settings(_)


@app.post("/api/source/probar")
def api_source_probar(_: dict = Depends(require_admin("config"))) -> dict:
    try:
        return dbf.probar(settings.source())
    except dbf.DbfError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Error probando la conexión: {e}")


@app.post("/api/botdb/probar")
def api_botdb_probar(_: dict = Depends(require_admin("config"))) -> dict:
    try:
        return botdb.probar_conexion(settings.bot_db_path())
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Error probando la BD del bot: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  Panel — Facturación  [perm: factura]
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/facturacion")
def api_facturacion_get(_: dict = Depends(require_admin("factura"))) -> dict:
    return settings.facturacion()


@app.post("/api/facturacion")
def api_facturacion_set(payload: dict, _: dict = Depends(require_admin("factura"))) -> dict:
    settings.save_facturacion(payload)
    return settings.facturacion()


@app.get("/api/facturacion/folio/{numcheque}")
def api_fact_folio(numcheque: int, _: dict = Depends(require_admin("factura"))) -> dict:
    return _build_comprobante(numcheque)


@app.get("/api/facturacion/ventas")
def api_fact_ventas(fecha: str = "hoy", _: dict = Depends(require_admin("factura"))) -> dict:
    return _comprobantes_dia(fecha)


# ══════════════════════════════════════════════════════════════════════════════
#  Panel — Importar  [perm: importar]
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/importar")
def api_importar(_: dict = Depends(require_admin("importar"))) -> dict:
    try:
        data = dbf.read_all(settings.source(), settings.dbf_encoding())
    except dbf.DbfError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Error leyendo DBF: {e}")
    resumen = store.reemplazar_todo(data["clientes"], data["direcciones"])
    return {"ok": True, "resumen": resumen, "dbf_stats": data["stats"]}


# ══════════════════════════════════════════════════════════════════════════════
#  Panel — Buscar (prueba)  [perm: buscar]
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/clientes/buscar")
def api_clientes_buscar(celular: str, _: dict = Depends(require_admin("buscar"))) -> dict:
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
                 _: dict = Depends(require_admin("buscar"))) -> dict:
    return store.listar_clientes(limit=min(limit, 200), offset=offset, q=q)


# ══════════════════════════════════════════════════════════════════════════════
#  Panel — Sincronizar  [perm: sync]
# ══════════════════════════════════════════════════════════════════════════════

def _bot_path() -> str:
    p = settings.bot_db_path()
    if not botdb.disponible(p):
        raise HTTPException(
            status_code=400,
            detail="No hay BD del bot accesible. Configura 'Ruta BD del bot' y "
                   "monta el SQLite del bot en el contenedor.")
    return p


@app.get("/api/sync/diff")
def api_sync_diff(_: dict = Depends(require_admin("sync"))) -> dict:
    path = _bot_path()
    idx = store.all_clientes()
    if not idx:
        raise HTTPException(status_code=400,
                            detail="El índice está vacío. Haz primero una importación masiva.")
    bot = botdb.leer_clientes(path)
    return sync.diff(idx, bot)


@app.post("/api/sync/aplicar")
def api_sync_aplicar(payload: dict, _: dict = Depends(require_admin("sync"))) -> dict:
    path = _bot_path()
    acciones = payload.get("acciones") or []
    if not acciones:
        raise HTTPException(status_code=400, detail="No hay acciones que aplicar")
    idx = store.all_clientes()
    return sync.aplicar(path, idx, acciones)


# ══════════════════════════════════════════════════════════════════════════════
#  Panel — Tokens API  [perm: tokens]
# ══════════════════════════════════════════════════════════════════════════════

def _mask_token(t: dict) -> dict:
    """Devuelve el token con el valor enmascarado (solo preview de 8 chars)."""
    raw = t.get("token", "")
    return {k: v for k, v in t.items() if k != "token"} | {"token_preview": raw[:8] + "…"}


@app.get("/api/tokens")
def api_tokens_list(_: dict = Depends(require_admin("tokens"))) -> list:
    return [_mask_token(t) for t in settings.api_tokens()]


@app.post("/api/tokens")
def api_tokens_create(payload: dict, _: dict = Depends(require_admin("tokens"))) -> dict:
    name = str(payload.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=400, detail="El campo 'name' es requerido")
    permisos = payload.get("permisos", list(settings.TOKEN_PERMS))
    return settings.create_api_token(name, permisos)   # devuelve token completo solo en creación


@app.patch("/api/tokens/{tid}")
def api_tokens_update(tid: str, payload: dict,
                      _: dict = Depends(require_admin("tokens"))) -> dict:
    t = settings.update_api_token(tid, payload)
    if not t:
        raise HTTPException(status_code=404, detail="Token no encontrado")
    return _mask_token(t)


@app.post("/api/tokens/{tid}/regenerar")
def api_tokens_regenerar(tid: str, _: dict = Depends(require_admin("tokens"))) -> dict:
    t = settings.regenerar_api_token(tid)
    if not t:
        raise HTTPException(status_code=404, detail="Token no encontrado")
    return t   # devuelve token completo tras regenerar


@app.delete("/api/tokens/{tid}")
def api_tokens_delete(tid: str, _: dict = Depends(require_admin("tokens"))) -> dict:
    if not settings.delete_api_token(tid):
        raise HTTPException(status_code=404, detail="Token no encontrado")
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════════
#  Panel — Usuarios admin  [perm: usuarios]
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/usuarios")
def api_usuarios_list(_: dict = Depends(require_admin("usuarios"))) -> list:
    return settings.admin_users()


@app.post("/api/usuarios")
def api_usuarios_create(payload: dict, _: dict = Depends(require_admin("usuarios"))) -> dict:
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="username y password son requeridos")
    if any(u["username"] == username for u in settings.admin_users()):
        raise HTTPException(status_code=409, detail="El usuario ya existe")
    permisos = payload.get("permisos", [])
    return settings.create_admin_user(username, password, permisos)


@app.patch("/api/usuarios/{username}")
def api_usuarios_update(username: str, payload: dict,
                        _: dict = Depends(require_admin("usuarios"))) -> dict:
    u = settings.update_admin_user(username, payload)
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return u


@app.delete("/api/usuarios/{username}")
def api_usuarios_delete(username: str, _: dict = Depends(require_admin("usuarios"))) -> dict:
    if not settings.delete_admin_user(username):
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════════
#  Startup
# ══════════════════════════════════════════════════════════════════════════════

@app.on_event("startup")
def _startup() -> None:
    settings.load()
    store.init()
