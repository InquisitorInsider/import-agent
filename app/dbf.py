"""Lectura, validación y normalización de las tablas DBF del sistema antiguo.

Tablas (FoxPro, codificación Windows ANSI = cp1252):

  clientesdomicilio.dbf
    IDCLIENTE  (C,15)  -> el CELULAR del cliente (llave de relación)
    NOMBRE     (C,150) -> nombre del cliente (campo más importante)
    TELEFONO1..5       -> teléfonos; TELEFONO1 debería coincidir con IDCLIENTE
    EMAIL, CUMPLEAÑOS, COMENTARIO, ...

  direccionesdomicilio.dbf
    IDCLIENTE  (C,15)  -> celular del cliente (FK hacia clientesdomicilio)
    CALLE      (C,80)  -> la dirección (campo más importante)
    REFERENCIA (C,250) -> referencia (suele venir vacío, pero se importa si hay)
    DELEGACION, CIUDAD, ESTADO, PAIS, NUMEROEXTE, NUMEROINTE, ...

Reglas de validación (definidas por Alex):
  - Un IDCLIENTE solo se acepta si tiene EXACTAMENTE N dígitos (N=9) y es
    100% numérico. Todo lo demás se omite.
  - Esa misma regla aplica al IDCLIENTE de la tabla de direcciones, porque la
    relación cliente<->dirección se hace por ese campo (el teléfono).

El agente NUNCA escribe en los DBF: los abre en solo lectura.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile

from dbfread import DBF

from . import config


# ----------------------------- normalización -----------------------------
_NON_DIGITS = re.compile(r"\D+")


def only_digits(value: str | None) -> str:
    return _NON_DIGITS.sub("", value or "")


def normalize_phone(value: str | None, digits: int | None = None,
                    country: str | None = None) -> str | None:
    """Devuelve el celular normalizado a EXACTAMENTE `digits` dígitos, o None.

    Acepta entradas variadas que pueden venir del bot o del DBF:
        '942432739'                -> '942432739'
        '51942432739'              -> '942432739'  (quita prefijo país)
        '51942432739@s.whatsapp.net' / '...@c.us' -> '942432739'
        ' 942 432 739 '            -> '942432739'
    Si tras limpiar no quedan exactamente `digits` dígitos válidos, None.
    """
    digits = digits or config.PHONE_DIGITS
    country = country if country is not None else config.COUNTRY_CODE
    d = only_digits(value)
    if not d:
        return None
    # Quitar prefijo de país si viene pegado (p. ej. 51 + 9 dígitos = 11).
    if country and len(d) == digits + len(country) and d.startswith(country):
        d = d[len(country):]
    # Caso bot: a veces el celular_real ya viene como 51XXXXXXXXX.
    if country and len(d) > digits and d.startswith(country):
        rest = d[len(country):]
        if len(rest) == digits:
            d = rest
    return d if len(d) == digits and d.isdigit() else None


def _txt(value) -> str:
    return (value or "").strip() if isinstance(value, str) else (
        "" if value is None else str(value).strip())


# ----------------------------- obtención de archivos -----------------------------
class DbfError(RuntimeError):
    pass


def _smb_fetch(src: dict, filename: str, dest_dir: str) -> str:
    """Descarga un archivo del recurso SMB a dest_dir con smbclient. Devuelve la ruta local."""
    host = src.get("smb_host")
    share = src.get("smb_share")
    if not host or not share:
        raise DbfError("Origen SMB sin host o recurso (smb_host/smb_share)")
    remote = filename
    sub = (src.get("smb_path") or "").strip().strip("/").replace("/", "\\")
    if sub:
        remote = f"{sub}\\{filename}"
    local = os.path.join(dest_dir, filename)

    cmd = ["smbclient", f"//{host}/{share}"]
    user = src.get("smb_user")
    if user:
        cmd += ["-U", f"{user}%{src.get('smb_pass', '')}"]
    else:
        cmd += ["-N"]
    if src.get("smb_domain"):
        cmd += ["-W", src["smb_domain"]]
    if src.get("smb_ip"):
        cmd += ["-I", src["smb_ip"]]
    cmd += ["-c", f'get "{remote}" "{local}"']

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0 or not os.path.exists(local):
        raise DbfError(
            f"No se pudo descargar {filename} por SMB "
            f"(code {proc.returncode}): {(proc.stderr or proc.stdout).strip()}"
        )
    return local


def resolve_files(src: dict, workdir: str) -> tuple[str, str]:
    """Resuelve las rutas locales de los dos DBF según el origen configurado.

    - source_type 'local': los archivos ya están en una carpeta montada.
    - source_type 'smb'  : se descargan del recurso compartido a `workdir`.
    Devuelve (ruta_clientes, ruta_direcciones).
    """
    cli_name = src.get("clientes_file") or "clientesdomicilio.dbf"
    dir_name = src.get("direcciones_file") or "direccionesdomicilio.dbf"
    stype = (src.get("source_type") or "smb").lower()

    if stype == "local":
        base = src.get("local_dir") or ""
        cli = os.path.join(base, cli_name)
        dirp = os.path.join(base, dir_name)
        if not os.path.exists(cli):
            raise DbfError(f"No existe el archivo de clientes: {cli}")
        if not os.path.exists(dirp):
            raise DbfError(f"No existe el archivo de direcciones: {dirp}")
        return cli, dirp

    # SMB
    os.makedirs(workdir, exist_ok=True)
    cli = _smb_fetch(src, cli_name, workdir)
    dirp = _smb_fetch(src, dir_name, workdir)
    return cli, dirp


# ----------------------------- lectura + validación -----------------------------
def _open(path: str, encoding: str):
    return DBF(path, encoding=encoding, ignore_missing_memofile=True,
               char_decode_errors="replace")


def read_clientes(path: str, encoding: str | None = None) -> dict:
    """Lee la tabla de clientes y devuelve filas válidas + estadísticas.

    Retorna {"clientes": [ {celular, nombre, telefono, email} ... ],
             "stats": {...}}
    Solo incluye filas con idcliente de N dígitos numéricos. Las que además no
    tienen nombre se cuentan aparte (sin_nombre) pero NO se incluyen, porque el
    objetivo es justamente obtener el nombre real.
    """
    encoding = encoding or config.DBF_ENCODING
    out = []
    total = sin_id = sin_nombre = tel_ok = tel_dif = 0
    vistos: set[str] = set()
    for r in _open(path, encoding):
        total += 1
        cel = normalize_phone(_txt(r.get("IDCLIENTE")))
        if not cel:
            sin_id += 1
            continue
        nombre = _txt(r.get("NOMBRE"))
        tel = _txt(r.get("TELEFONO1"))
        if tel:
            if only_digits(tel) == cel:
                tel_ok += 1
            else:
                tel_dif += 1
        if len(nombre) < 2:
            sin_nombre += 1
            continue
        if cel in vistos:        # dedup: nos quedamos con la primera aparición
            continue
        vistos.add(cel)
        out.append({
            "celular": cel,
            "nombre": nombre,
            "telefono": tel,
            "email": _txt(r.get("EMAIL")),
        })
    return {
        "clientes": out,
        "stats": {
            "total_filas": total,
            "validos_con_nombre": len(out),
            "omitidos_idcliente_invalido": sin_id,
            "omitidos_sin_nombre": sin_nombre,
            "telefono1_coincide": tel_ok,
            "telefono1_distinto": tel_dif,
        },
    }


def read_direcciones(path: str, encoding: str | None = None) -> dict:
    """Lee la tabla de direcciones y devuelve filas válidas + estadísticas.

    Retorna {"direcciones": [ {celular, calle, referencia, ciudad, orden} ... ],
             "stats": {...}}
    """
    encoding = encoding or config.DBF_ENCODING
    out = []
    total = sin_id = sin_calle = con_ref = 0
    orden: dict[str, int] = {}
    for r in _open(path, encoding):
        total += 1
        cel = normalize_phone(_txt(r.get("IDCLIENTE")))
        if not cel:
            sin_id += 1
            continue
        calle = _txt(r.get("CALLE"))
        ref = _txt(r.get("REFERENCIA"))
        if not calle and not ref:
            sin_calle += 1
            continue
        if ref:
            con_ref += 1
        orden[cel] = orden.get(cel, 0) + 1
        out.append({
            "celular": cel,
            "calle": calle,
            "referencia": ref,
            "delegacion": _txt(r.get("DELEGACION")),
            "ciudad": _txt(r.get("CIUDAD")),
            "numero_ext": _txt(r.get("NUMEROEXTE")),
            "orden": orden[cel],
        })
    return {
        "direcciones": out,
        "stats": {
            "total_filas": total,
            "validas": len(out),
            "omitidas_idcliente_invalido": sin_id,
            "omitidas_sin_calle": sin_calle,
            "con_referencia": con_ref,
            "clientes_distintos": len(orden),
        },
    }


def read_all(src: dict, encoding: str | None = None) -> dict:
    """Resuelve y lee ambas tablas. Devuelve {clientes, direcciones, stats}."""
    encoding = encoding or config.DBF_ENCODING
    with tempfile.TemporaryDirectory(prefix="dbf_") as tmp:
        cli_path, dir_path = resolve_files(src, tmp)
        cli = read_clientes(cli_path, encoding)
        dirs = read_direcciones(dir_path, encoding)
    return {
        "clientes": cli["clientes"],
        "direcciones": dirs["direcciones"],
        "stats": {"clientes": cli["stats"], "direcciones": dirs["stats"]},
    }
