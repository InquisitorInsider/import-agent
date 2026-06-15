"""Ajustes en caliente, persistidos en /data/settings.json.

Editable desde la interfaz web. Los valores de config (semilla) solo se usan la
primera vez para crear el archivo.

Estructura:
{
  "source": { source_type, local_dir, smb_host, smb_share, smb_path,
              smb_user, smb_pass, smb_domain, smb_ip,
              clientes_file, direcciones_file },
  "bot_db_path": "/bot/pedidos.db",
  "lookup_token": "",
  "dbf_encoding": "cp1252"
}
"""
from __future__ import annotations

import json
import os
import threading

from . import config

_PATH = os.path.join(config.DATA_DIR, "settings.json")
_lock = threading.RLock()
_data: dict = {}

_SOURCE_KEYS = ["source_type", "local_dir", "smb_host", "smb_share", "smb_path",
                "smb_user", "smb_pass", "smb_domain", "smb_ip",
                "clientes_file", "direcciones_file"]


def _coerce_source(s: dict) -> dict:
    out = {k: str(s.get(k, "")).strip() for k in _SOURCE_KEYS}
    out["source_type"] = (out["source_type"] or "smb").lower()
    out["smb_domain"] = out["smb_domain"] or "WORKGROUP"
    out["clientes_file"] = out["clientes_file"] or "clientesdomicilio.dbf"
    out["direcciones_file"] = out["direcciones_file"] or "direccionesdomicilio.dbf"
    return out


def _seed() -> dict:
    return {
        "source": _coerce_source(config.SEED_SOURCE),
        "bot_db_path": config.SEED_BOT_DB,
        "lookup_token": config.LOOKUP_TOKEN,
        "dbf_encoding": config.DBF_ENCODING,
    }


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
        except (OSError, json.JSONDecodeError):
            pass
    _data = d
    _persist()


def _persist() -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    tmp = _PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _PATH)


# ----------------------------- getters -----------------------------
def source() -> dict:
    return dict(_data.get("source", {}))


def bot_db_path() -> str:
    return _data.get("bot_db_path", "")


def lookup_token() -> str:
    return _data.get("lookup_token", "")


def dbf_encoding() -> str:
    return _data.get("dbf_encoding", "cp1252")


# ----------------------------- setters (desde la UI) -----------------------------
def save_source(s: dict) -> None:
    s = _coerce_source(s)
    with _lock:
        prev = _data.get("source", {})
        # secreto vacío => conservar el guardado
        if not s.get("smb_pass"):
            s["smb_pass"] = prev.get("smb_pass", "")
        _data["source"] = s
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


# ----------------------------- vista pública (oculta secretos) -----------------------------
def public() -> dict:
    s = dict(_data.get("source", {}))
    s["smb_pass"] = "***" if s.get("smb_pass") else ""
    return {
        "source": s,
        "bot_db_path": _data.get("bot_db_path", ""),
        "lookup_token": "***" if _data.get("lookup_token") else "",
        "dbf_encoding": _data.get("dbf_encoding", "cp1252"),
    }


load()
