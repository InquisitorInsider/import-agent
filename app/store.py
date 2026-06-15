"""Índice limpio propio del agente (SQLite en /data/index.db).

Aquí vive el resultado de la "importación masiva": los clientes y direcciones
del DBF ya validados y normalizados. El bot consulta este índice en runtime
(rápido y desacoplado del archivo DBF, que puede estar bloqueado por el sistema
antiguo). Re-ejecutar la importación = mantener el índice sincronizado.

Esquema:
  clientes(celular PK, nombre, telefono, email, updated_at)
  direcciones(id PK, celular, calle, referencia, ciudad, numero_ext, orden)
  meta(clave PK, valor)        -- p. ej. ultima_importacion, conteos
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime

from . import config

_PATH = os.path.join(config.DATA_DIR, "index.db")
_lock = threading.RLock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS clientes (
    celular    TEXT PRIMARY KEY,
    nombre     TEXT NOT NULL,
    telefono   TEXT,
    email      TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS direcciones (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    celular    TEXT NOT NULL,
    calle      TEXT,
    referencia TEXT,
    ciudad     TEXT,
    numero_ext TEXT,
    orden      INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_dir_celular ON direcciones(celular);
CREATE TABLE IF NOT EXISTS meta (
    clave TEXT PRIMARY KEY,
    valor TEXT
);
"""


def _conn() -> sqlite3.Connection:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    c = sqlite3.connect(_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init() -> None:
    with _lock, _conn() as c:
        c.executescript(_SCHEMA)


# ----------------------------- importación masiva -----------------------------
def reemplazar_todo(clientes: list[dict], direcciones: list[dict]) -> dict:
    """Reemplaza el índice completo con lo leído del DBF (idempotente).

    Estrategia simple y segura: vaciar y recargar dentro de una transacción.
    Así el índice siempre refleja exactamente el DBF actual (altas, bajas y
    cambios). Devuelve un resumen con conteos.
    """
    ahora = datetime.now().isoformat(timespec="seconds")
    with _lock, _conn() as c:
        c.executescript(_SCHEMA)
        c.execute("DELETE FROM clientes")
        c.execute("DELETE FROM direcciones")
        c.executemany(
            "INSERT OR REPLACE INTO clientes (celular, nombre, telefono, email, updated_at) "
            "VALUES (:celular, :nombre, :telefono, :email, :ahora)",
            [{**cl, "ahora": ahora} for cl in clientes],
        )
        # Solo direcciones cuyo cliente existe en el índice (integridad por teléfono).
        cels = {cl["celular"] for cl in clientes}
        dirs_ok = [d for d in direcciones if d["celular"] in cels]
        c.executemany(
            "INSERT INTO direcciones (celular, calle, referencia, ciudad, numero_ext, orden) "
            "VALUES (:celular, :calle, :referencia, :ciudad, :numero_ext, :orden)",
            dirs_ok,
        )
        resumen = {
            "clientes": len(clientes),
            "direcciones": len(dirs_ok),
            "direcciones_huerfanas_omitidas": len(direcciones) - len(dirs_ok),
            "fecha": ahora,
        }
        c.execute(
            "INSERT OR REPLACE INTO meta (clave, valor) VALUES ('ultima_importacion', ?)",
            (json.dumps(resumen, ensure_ascii=False),),
        )
    return resumen


# ----------------------------- consultas -----------------------------
def buscar_cliente(celular: str) -> dict | None:
    """Busca un cliente por celular normalizado e incluye sus direcciones."""
    with _lock, _conn() as c:
        row = c.execute("SELECT * FROM clientes WHERE celular=?", (celular,)).fetchone()
        if not row:
            return None
        dirs = c.execute(
            "SELECT calle, referencia, ciudad, numero_ext, orden FROM direcciones "
            "WHERE celular=? ORDER BY orden", (celular,),
        ).fetchall()
    cli = dict(row)
    cli["direcciones"] = [dict(d) for d in dirs]
    return cli


def listar_clientes(limit: int = 50, offset: int = 0, q: str = "") -> dict:
    q = (q or "").strip()
    with _lock, _conn() as c:
        if q:
            like = f"%{q}%"
            total = c.execute(
                "SELECT COUNT(*) FROM clientes WHERE nombre LIKE ? OR celular LIKE ?",
                (like, like),
            ).fetchone()[0]
            rows = c.execute(
                "SELECT celular, nombre, telefono FROM clientes "
                "WHERE nombre LIKE ? OR celular LIKE ? ORDER BY nombre LIMIT ? OFFSET ?",
                (like, like, limit, offset),
            ).fetchall()
        else:
            total = c.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
            rows = c.execute(
                "SELECT celular, nombre, telefono FROM clientes "
                "ORDER BY nombre LIMIT ? OFFSET ?", (limit, offset),
            ).fetchall()
    return {"total": total, "items": [dict(r) for r in rows]}


def all_clientes() -> dict[str, dict]:
    """Devuelve {celular: {nombre, direcciones[...]}} para el motor de diff."""
    with _lock, _conn() as c:
        clientes = {r["celular"]: {"celular": r["celular"], "nombre": r["nombre"],
                                   "direcciones": []}
                    for r in c.execute("SELECT celular, nombre FROM clientes")}
        for d in c.execute("SELECT celular, calle, referencia, orden FROM direcciones ORDER BY orden"):
            if d["celular"] in clientes:
                clientes[d["celular"]]["direcciones"].append(dict(d))
    return clientes


def stats() -> dict:
    with _lock, _conn() as c:
        c.executescript(_SCHEMA)
        nc = c.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
        nd = c.execute("SELECT COUNT(*) FROM direcciones").fetchone()[0]
        meta = c.execute("SELECT valor FROM meta WHERE clave='ultima_importacion'").fetchone()
    ultima = json.loads(meta[0]) if meta else None
    return {"clientes": nc, "direcciones": nd, "ultima_importacion": ultima}
