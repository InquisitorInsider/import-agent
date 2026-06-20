"""Ajustes en caliente, persistidos en /data/settings.json.

Editable desde la interfaz web. Los valores de config (semilla) solo se usan la
primera vez para crear el archivo.

Estructura:
{
  "source": { source_type, local_dir, smb_host, smb_share, smb_path,
              smb_user, smb_pass, smb_domain, smb_ip,
              clientes_file, direcciones_file },
  "bot_db_path": "/bot/pedidos.db",
  "lookup_token": "",           # campo heredado, se migra a api_tokens al cargar
  "dbf_encoding": "cp1252",
  "api_tokens": [               # tokens para clientes HTTP (bot, facturador, etc.)
    { "id": "…", "name": "Bot WhatsApp", "token": "…",
      "permisos": ["clientes", "facturacion"], "activo": true, "creado": "…" }
  ],
  "admin_users": [              # usuarios del panel web
    { "username": "admin", "password_hash": "salt:hash",
      "permisos": ["*"], "activo": true, "creado": "…" }
  ]
}
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
from datetime import datetime, timezone

from . import config

_PATH = os.path.join(config.DATA_DIR, "settings.json")
_lock = threading.RLock()
_data: dict = {}

_SOURCE_KEYS = ["source_type", "local_dir", "smb_host", "smb_share", "smb_path",
                "smb_user", "smb_pass", "smb_domain", "smb_ip",
                "clientes_file", "direcciones_file"]

TOKEN_PERMS = ("clientes", "facturacion")
USER_PERMS  = ("config", "importar", "buscar", "sync", "factura", "tokens", "usuarios", "*")


# ── Utilidades de contraseña (pbkdf2-sha256, stdlib) ──────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash_pw(pw: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100_000).hex()
    return f"{salt}:{h}"


def _check_pw(pw: str, stored: str) -> bool:
    try:
        salt, h = stored.split(":", 1)
        return secrets.compare_digest(
            hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100_000).hex(), h)
    except Exception:
        return False


# ── Coerciones de estructura ───────────────────────────────────────────────────

def _coerce_source(s: dict) -> dict:
    out = {k: str(s.get(k, "")).strip() for k in _SOURCE_KEYS}
    out["source_type"] = (out["source_type"] or "smb").lower()
    out["smb_domain"] = out["smb_domain"] or "WORKGROUP"
    out["clientes_file"] = out["clientes_file"] or "clientesdomicilio.dbf"
    out["direcciones_file"] = out["direcciones_file"] or "direccionesdomicilio.dbf"
    return out


def _num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _seed_facturacion() -> dict:
    return {
        "emisor": {
            "ruc": "", "razon_social": "", "nombre_comercial": "",
            "domicilio_fiscal": "", "ubigeo": "",
            "distrito": "", "provincia": "", "departamento": "",
        },
        "series": {"boleta": "B001", "factura": "F001"},
        "moneda": "PEN",
        "igv_reglas": [
            {"desde": "2022-09-01", "hasta": "2025-12-31", "igv": 8.0, "ipm": 2.0},
            {"desde": "2026-01-01", "hasta": "2026-12-31", "igv": 8.0, "ipm": 2.5},
        ],
        "formas_pago": [
            {"codigo": "EF", "nombre": "Efectivo"}, {"codigo": "MC", "nombre": "Izipay"},
            {"codigo": "11", "nombre": "Culqi"}, {"codigo": "13", "nombre": "Plin"},
            {"codigo": "08", "nombre": "Yape"}, {"codigo": "14", "nombre": "Falabella"},
            {"codigo": "12", "nombre": "Niubiz"}, {"codigo": "09", "nombre": "Tunki"},
            {"codigo": "10", "nombre": "Didi"}, {"codigo": "CR", "nombre": "Credito"},
            {"codigo": "DLL", "nombre": "Dolares"}, {"codigo": "VAL", "nombre": "Vales"},
            {"codigo": "VISA", "nombre": "Vendemas"}, {"codigo": "AMEX", "nombre": "American Express"},
        ],
        "catalogos": {
            "tipo_boleta": "03", "tipo_factura": "01",
            "afectacion_igv": "10", "unidad_medida": "NIU",
            "doc_dni": "1", "doc_ruc": "6", "doc_sin": "0",
            "forma_pago_sunat": "Contado", "umbral_dni_boleta": 700,
        },
    }


def _coerce_facturacion(f: dict) -> dict:
    seed = _seed_facturacion()
    f = f or {}
    em = f.get("emisor") or {}
    emisor = {k: str(em.get(k, seed["emisor"][k]) or "").strip() for k in seed["emisor"]}
    ser = f.get("series") or {}
    series = {"boleta": (str(ser.get("boleta", "B001")).strip() or "B001"),
              "factura": (str(ser.get("factura", "F001")).strip() or "F001")}
    reglas = []
    for r in (f.get("igv_reglas") or seed["igv_reglas"]):
        reglas.append({"desde": str(r.get("desde", "")).strip(),
                       "hasta": str(r.get("hasta", "")).strip(),
                       "igv": _num(r.get("igv")), "ipm": _num(r.get("ipm"))})
    pagos = []
    for p in (f.get("formas_pago") or seed["formas_pago"]):
        cod = str(p.get("codigo", "")).strip()
        if cod:
            pagos.append({"codigo": cod, "nombre": str(p.get("nombre", "")).strip()})
    cat_in = f.get("catalogos") or {}
    catalogos = {k: cat_in.get(k, seed["catalogos"][k]) for k in seed["catalogos"]}
    catalogos["umbral_dni_boleta"] = _num(catalogos.get("umbral_dni_boleta"), 700)
    return {"emisor": emisor, "series": series,
            "moneda": (str(f.get("moneda", "PEN")).strip() or "PEN"),
            "igv_reglas": reglas, "formas_pago": pagos, "catalogos": catalogos}


def _seed() -> dict:
    return {
        "source": _coerce_source(config.SEED_SOURCE),
        "bot_db_path": config.SEED_BOT_DB,
        "lookup_token": config.LOOKUP_TOKEN,
        "dbf_encoding": config.DBF_ENCODING,
        "facturacion": _seed_facturacion(),
        "api_tokens": [],
        "admin_users": [],
    }


# ── Carga y persistencia ───────────────────────────────────────────────────────

def load() -> None:
    global _data
    d = _seed()
    if os.path.exists(_PATH):
        try:
            with open(_PATH, encoding="utf-8") as f:
                stored = json.load(f)
            if "source" in stored:
                d["source"] = _coerce_source(stored["source"])
            d["bot_db_path"] = str(stored.get("bot_db_path", d["bot_db_path"])).strip()
            d["lookup_token"] = str(stored.get("lookup_token", d["lookup_token"])).strip()
            d["dbf_encoding"] = str(stored.get("dbf_encoding", d["dbf_encoding"])).strip() or "cp1252"
            if "facturacion" in stored:
                d["facturacion"] = _coerce_facturacion(stored["facturacion"])
            d["api_tokens"]   = stored.get("api_tokens", [])
            d["admin_users"]  = stored.get("admin_users", [])
        except (OSError, json.JSONDecodeError):
            pass

    # Migrar token heredado (campo único) → lista de api_tokens
    if d["lookup_token"] and not d["api_tokens"]:
        d["api_tokens"] = [{
            "id": "leg-" + secrets.token_hex(4),
            "name": "Token heredado (migrado)",
            "token": d["lookup_token"],
            "permisos": ["clientes", "facturacion"],
            "activo": True,
            "creado": _now(),
        }]
        d["lookup_token"] = ""

    _data = d
    _persist()


def _persist() -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    tmp = _PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _PATH)


# ── Getters ────────────────────────────────────────────────────────────────────

def source() -> dict:
    return dict(_data.get("source", {}))


def bot_db_path() -> str:
    return _data.get("bot_db_path", "")


def lookup_token() -> str:
    return _data.get("lookup_token", "")


def dbf_encoding() -> str:
    return _data.get("dbf_encoding", "cp1252")


def facturacion() -> dict:
    return _coerce_facturacion(_data.get("facturacion", {}))


def api_tokens() -> list:
    return list(_data.get("api_tokens", []))


def admin_users() -> list:
    """Lista de usuarios (sin password_hash)."""
    return [{k: v for k, v in u.items() if k != "password_hash"}
            for u in _data.get("admin_users", [])]


# ── Auth ───────────────────────────────────────────────────────────────────────

def has_any_api_token() -> bool:
    """True si hay al menos un token activo configurado."""
    return any(t.get("activo") for t in _data.get("api_tokens", []))


def verify_api_token(token: str, perm: str) -> bool:
    """Devuelve True si el token dado existe, está activo y tiene el permiso."""
    for t in _data.get("api_tokens", []):
        if not t.get("activo"):
            continue
        stored = t.get("token", "")
        if len(token) == len(stored) and secrets.compare_digest(token, stored):
            p = t.get("permisos", [])
            return "*" in p or perm in p
    return False


def verify_admin(username: str, password: str) -> dict | None:
    """Autentica un usuario del panel.

    Siempre comprueba primero las variables de entorno ADMIN_USER/ADMIN_PASSWORD
    (sirven como clave maestra aunque haya usuarios guardados).
    """
    if (config.ADMIN_PASSWORD
            and secrets.compare_digest(username, config.ADMIN_USER)
            and secrets.compare_digest(password, config.ADMIN_PASSWORD)):
        return {"username": username, "permisos": ["*"], "activo": True}
    for u in _data.get("admin_users", []):
        if u.get("activo") and u["username"] == username:
            if _check_pw(password, u.get("password_hash", "")):
                return {k: v for k, v in u.items() if k != "password_hash"}
    return None


# ── Mutaciones: tokens API ─────────────────────────────────────────────────────

def create_api_token(name: str, permisos: list) -> dict:
    permisos = [p for p in permisos if p in TOKEN_PERMS]
    t = {
        "id": secrets.token_hex(8),
        "name": name.strip(),
        "token": secrets.token_urlsafe(32),
        "permisos": permisos,
        "activo": True,
        "creado": _now(),
    }
    with _lock:
        _data.setdefault("api_tokens", []).append(t)
        _persist()
    return t


def regenerar_api_token(tid: str) -> dict | None:
    with _lock:
        for i, t in enumerate(_data.get("api_tokens", [])):
            if t["id"] == tid:
                _data["api_tokens"][i] = {**t, "token": secrets.token_urlsafe(32)}
                _persist()
                return _data["api_tokens"][i]
    return None


def update_api_token(tid: str, patch: dict) -> dict | None:
    with _lock:
        for i, t in enumerate(_data.get("api_tokens", [])):
            if t["id"] == tid:
                updated = dict(t)
                if "name" in patch:
                    updated["name"] = str(patch["name"]).strip()
                if "activo" in patch:
                    updated["activo"] = bool(patch["activo"])
                if "permisos" in patch:
                    updated["permisos"] = [p for p in patch["permisos"] if p in TOKEN_PERMS]
                _data["api_tokens"][i] = updated
                _persist()
                return updated
    return None


def delete_api_token(tid: str) -> bool:
    with _lock:
        prev = _data.get("api_tokens", [])
        new = [t for t in prev if t["id"] != tid]
        if len(new) == len(prev):
            return False
        _data["api_tokens"] = new
        _persist()
        return True


# ── Mutaciones: usuarios admin ─────────────────────────────────────────────────

def create_admin_user(username: str, password: str, permisos: list) -> dict:
    permisos = [p for p in permisos if p in USER_PERMS]
    u = {
        "username": username.strip(),
        "password_hash": _hash_pw(password),
        "permisos": permisos,
        "activo": True,
        "creado": _now(),
    }
    with _lock:
        _data.setdefault("admin_users", []).append(u)
        _persist()
    return {k: v for k, v in u.items() if k != "password_hash"}


def update_admin_user(username: str, patch: dict) -> dict | None:
    with _lock:
        for i, u in enumerate(_data.get("admin_users", [])):
            if u["username"] == username:
                updated = dict(u)
                if patch.get("password"):
                    updated["password_hash"] = _hash_pw(patch["password"])
                if "permisos" in patch:
                    updated["permisos"] = [p for p in patch["permisos"] if p in USER_PERMS]
                if "activo" in patch:
                    updated["activo"] = bool(patch["activo"])
                _data["admin_users"][i] = updated
                _persist()
                return {k: v for k, v in updated.items() if k != "password_hash"}
    return None


def delete_admin_user(username: str) -> bool:
    with _lock:
        prev = _data.get("admin_users", [])
        new = [u for u in prev if u["username"] != username]
        if len(new) == len(prev):
            return False
        _data["admin_users"] = new
        _persist()
        return True


# ── Setters heredados (desde la UI de Configuración) ──────────────────────────

def save_source(s: dict) -> None:
    s = _coerce_source(s)
    with _lock:
        prev = _data.get("source", {})
        if not s.get("smb_pass"):
            s["smb_pass"] = prev.get("smb_pass", "")
        _data["source"] = s
        _persist()


def save_facturacion(payload: dict) -> None:
    with _lock:
        _data["facturacion"] = _coerce_facturacion(payload)
        _persist()


def save_globals(payload: dict) -> None:
    with _lock:
        if "bot_db_path" in payload:
            _data["bot_db_path"] = str(payload["bot_db_path"]).strip()
        if "lookup_token" in payload:
            _data["lookup_token"] = str(payload["lookup_token"]).strip()
        if "dbf_encoding" in payload:
            _data["dbf_encoding"] = str(payload["dbf_encoding"]).strip() or "cp1252"
        _persist()


# ── Vista pública (oculta secretos) ───────────────────────────────────────────

def public() -> dict:
    s = dict(_data.get("source", {}))
    s["smb_pass"] = "***" if s.get("smb_pass") else ""
    return {
        "source": s,
        "bot_db_path": _data.get("bot_db_path", ""),
        "lookup_token": "***" if _data.get("lookup_token") else "",
        "dbf_encoding": _data.get("dbf_encoding", "cp1252"),
        "facturacion": facturacion(),
    }


load()
