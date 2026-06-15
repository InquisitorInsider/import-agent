"""Acceso al SQLite del WhatsApp bot (solo para el panel de sincronización).

La búsqueda en runtime (/clientes/buscar) NO usa esto: el bot llama por HTTP y
el agente responde desde su índice limpio. Este módulo solo se usa cuando, desde
el panel, quieres COMPARAR el índice del DBF contra los clientes que ya existen
en el bot y, opcionalmente, corregir nombres/direcciones mal escritos.

Esquema relevante del bot:
  clientes(celular PK = LID de WhatsApp, nombre, celular_real, vetado, ...)
  direcciones(id PK, celular = LID, direccion, referencia, orden, activa, ...)

El cruce DBF<->bot se hace por `celular_real` normalizado a N dígitos (el DBF
guarda el número de 9 dígitos; el bot guarda 51XXXXXXXXX en celular_real).

IMPORTANTE: no se pueden CREAR clientes nuevos en el bot desde aquí, porque su
PK es el LID de WhatsApp que solo existe cuando la persona escribe. Por eso el
panel solo ACTUALIZA clientes que ya existen en el bot (los nuevos entran solos
en runtime vía /clientes/buscar). Nunca se tocan pedidos.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime

from . import config
from .dbf import normalize_phone


def disponible(path: str | None) -> bool:
    return bool(path) and os.path.exists(path)


def _conn(path: str) -> sqlite3.Connection:
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    return c


def leer_clientes(path: str) -> dict[str, dict]:
    """Devuelve {celular9: {lid, nombre, celular_real, direcciones[...]}}.

    Solo incluye clientes del bot que tienen celular_real válido (los únicos
    cruzables con el DBF por número).
    """
    out: dict[str, dict] = {}
    with _conn(path) as c:
        for r in c.execute("SELECT celular, nombre, celular_real FROM clientes"):
            cel9 = normalize_phone(r["celular_real"]) if r["celular_real"] else None
            if not cel9:
                continue
            out[cel9] = {
                "lid": r["celular"],
                "nombre": (r["nombre"] or "").strip(),
                "celular_real": r["celular_real"],
                "direcciones": [],
            }
        # mapear direcciones por LID
        por_lid = {v["lid"]: v for v in out.values()}
        try:
            for d in c.execute(
                "SELECT celular, direccion, referencia, orden FROM direcciones ORDER BY orden"
            ):
                v = por_lid.get(d["celular"])
                if v is not None:
                    v["direcciones"].append({
                        "calle": (d["direccion"] or "").strip(),
                        "referencia": (d["referencia"] or "").strip(),
                        "orden": d["orden"],
                    })
        except sqlite3.OperationalError:
            pass
    return out


def actualizar_nombre(path: str, lid: str, nombre: str) -> None:
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn(path) as c:
        c.execute(
            "UPDATE clientes SET nombre=?, updated_at=? WHERE celular=?",
            (nombre, ahora, lid),
        )
        c.commit()


def agregar_direccion(path: str, lid: str, calle: str, referencia: str = "") -> None:
    """Agrega una dirección al cliente del bot si no tiene ninguna parecida."""
    with _conn(path) as c:
        existentes = c.execute(
            "SELECT direccion FROM direcciones WHERE celular=?", (lid,)
        ).fetchall()
        norm = {(e["direccion"] or "").strip().lower() for e in existentes}
        if calle.strip().lower() in norm:
            return
        orden = (c.execute(
            "SELECT COALESCE(MAX(orden),0)+1 FROM direcciones WHERE celular=?", (lid,)
        ).fetchone()[0]) or 1
        c.execute(
            "INSERT INTO direcciones (celular, direccion, referencia, orden, activa, created_at) "
            "VALUES (?,?,?,?,1,?)",
            (lid, calle.strip(), referencia.strip(), orden,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        c.commit()
