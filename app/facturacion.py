"""Paso 2 + 3 — Lector de ventas del POS AMC y conversión al estándar SUNAT.

- Lee `cheques/cheqdet/chequespagos` (turno cerrado) y `tempcheques/tempcheqdet/
  tempchequespagos` (turno vigente) — SOLO LECTURA.
- Llaves: identidad de venta = `NUMCHEQUE` (folio cuenta). Detalle se une por el
  `FOLIO` interno dentro de la MISMA tabla (`cheqdet.FOLIODET = cheques.FOLIO`).
  Producto: `cheqdet.CLAVEPROD = productos.CLAVE` -> `DESCRIPCIO`.
- Reglas: se excluyen folios anulados (`CANCELADO`) y líneas a S/ 0.00
  (modificadores). El IGV se recalcula INVERSO por fecha desde el `TOTAL`.

Toda la parametrización (emisor, series, tasas de IGV por fecha, formas de pago,
catálogos) viene de la config editable en el panel (settings.facturacion()).

Nota de rendimiento: por ahora lee los DBF completos. La caché/sync local se
optimiza en un paso posterior; las tablas principales cambian solo al cerrar turno.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from dbfread import DBF

from . import dbf as dbflib

# ───────────────────────── helpers ─────────────────────────
def _abrir(path: str, encoding: str):
    return DBF(path, encoding=encoding, ignore_missing_memofile=True,
               char_decode_errors="replace")


def _f(v) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _txt(v) -> str:
    return v.strip() if isinstance(v, str) else ("" if v is None else str(v).strip())


def _r2(x) -> float:
    return float(Decimal(str(x)).quantize(Decimal("0.01"), ROUND_HALF_UP))


# ───────────────────────── monto en letras ─────────────────────────
_UNI = ["", "UNO", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO",
        "NUEVE", "DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE",
        "DIECISEIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE", "VEINTE"]
_DEC = ["", "", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA",
        "SETENTA", "OCHENTA", "NOVENTA"]
_CEN = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS",
        "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]


def _decenas(n: int) -> str:
    if n <= 20:
        return _UNI[n]
    d, u = divmod(n, 10)
    if d == 2:
        return "VEINTIUNO" if u == 1 else ("VEINTE" if u == 0 else "VEINTI" + _UNI[u])
    return _DEC[d] + (" Y " + _UNI[u] if u else "")


def _centenas(n: int) -> str:
    if n == 0:
        return ""
    if n == 100:
        return "CIEN"
    c, d = divmod(n, 100)
    out = _CEN[c]
    return (out + " " + _decenas(d)).strip() if d else out


def _miles(n: int) -> str:
    if n < 1000:
        return _centenas(n)
    miles, resto = divmod(n, 1000)
    pref = "MIL" if miles == 1 else _centenas(miles) + " MIL"
    return pref + (" " + _centenas(resto) if resto else "")


def num_a_letras(monto: float, moneda: str = "SOLES") -> str:
    entero = int(monto)
    dec = int(round((float(monto) - entero) * 100))
    if dec == 100:
        entero += 1
        dec = 0
    if entero == 0:
        palabras = "CERO"
    elif entero < 1_000_000:
        palabras = _miles(entero)
    else:
        mill, resto = divmod(entero, 1_000_000)
        palabras = ("UN MILLON" if mill == 1 else _miles(mill) + " MILLONES")
        palabras += (" " + _miles(resto) if resto else "")
    return f"{palabras} CON {dec:02d}/100 {moneda}"


# ───────────────────────── productos ─────────────────────────
def cargar_productos(path: str, encoding: str) -> dict:
    idx = {}
    if not os.path.exists(path):
        return idx
    for r in _abrir(path, encoding):
        idx[_txt(r.get("CLAVE"))] = {
            "desc": _txt(r.get("DESCRIPCIO")),
            "nofact": bool(r.get("NOFACTURAB")),
        }
    return idx


# ───────────────────────── productos + grupo (aislado de facturación) ─────
# Función independiente para el catálogo con categoría/grupo (consumida por
# horno-ruta80 vía /facturacion/productos). Deliberadamente NO reutiliza
# cargar_productos() ni el caché de facturación (_FACT_CACHE/_TABLAS/_MAIN):
# esos los usan en vivo los endpoints de facturación electrónica y no
# queremos que un cambio en el catálogo/grupo pueda afectar ese flujo.
_PROD_GRUPO_TABLAS = ["productos.dbf", "grupos.dbf"]


def resolver_dir_productos(src: dict, workdir: str) -> str:
    """Igual que resolver_dir() pero solo para productos.dbf/grupos.dbf, con
    su propio directorio de caché (no comparte nada con facturación)."""
    stype = (src.get("source_type") or "smb").lower()
    if stype == "local":
        return src.get("local_dir") or ""
    os.makedirs(workdir, exist_ok=True)
    for t in _PROD_GRUPO_TABLAS:
        try:
            dbflib._smb_fetch(src, t, workdir)
        except dbflib.DbfError:
            pass  # grupos.dbf es opcional: si falta, el producto queda sin grupo
    return workdir


def _upper_keys(r) -> dict:
    """productos.dbf y grupos.dbf no siguen la misma convención de mayúsculas
    para nombres de campo — normalizamos para no depender de eso."""
    return {str(k).upper(): v for k, v in dict(r).items()}


def productos_con_grupo(base_dir: str, encoding: str) -> list[dict]:
    """Catálogo de productos con su grupo resuelto (productos.dbf.GRUPO join
    grupos.dbf.CLAVE -> DESCRIPCIO). Devuelve una lista lista para exponer."""
    grupos: dict[str, str] = {}
    path_grupos = os.path.join(base_dir, "grupos.dbf")
    if os.path.exists(path_grupos):
        for r in _abrir(path_grupos, encoding):
            row = _upper_keys(r)
            clave = _txt(row.get("CLAVE"))
            if clave:
                grupos[clave] = _txt(row.get("DESCRIPCIO"))

    items: list[dict] = []
    path_productos = os.path.join(base_dir, "productos.dbf")
    if os.path.exists(path_productos):
        for r in _abrir(path_productos, encoding):
            row = _upper_keys(r)
            grupo_clave = _txt(row.get("GRUPO"))
            items.append({
                "codigo": _txt(row.get("CLAVE")),
                "descripcion": _txt(row.get("DESCRIPCIO")),
                "grupo": grupos.get(grupo_clave) or None,
                "activo": not bool(row.get("NOFACTURAB")),
            })
    return items


# ───────────────────────── tasa IGV por fecha ─────────────────────────
def tasa_por_fecha(fecha, reglas: list) -> tuple[float, float]:
    """Devuelve (igv%, ipm%) vigentes en la fecha de la venta."""
    d = fecha.date() if isinstance(fecha, datetime) else (fecha or date.today())
    for r in reglas:
        try:
            desde = datetime.strptime(r["desde"], "%Y-%m-%d").date() if r.get("desde") else date.min
            hasta = datetime.strptime(r["hasta"], "%Y-%m-%d").date() if r.get("hasta") else date.max
        except (ValueError, KeyError):
            continue
        if desde <= d <= hasta:
            return _f(r.get("igv")), _f(r.get("ipm"))
    return 0.0, 0.0


# ───────────────────────── lectura de una venta (Paso 2) ─────────────────────────
_FUENTES = [
    ("vigente", "tempcheques.dbf", "tempcheqdet.dbf", "tempchequespagos.dbf"),
    ("cerrado", "cheques.dbf", "cheqdet.dbf", "chequespagos.dbf"),
]


def leer_venta(base_dir: str, numcheque, encoding: str) -> dict | None:
    """Busca la venta por NUMCHEQUE en turno vigente (temp) y luego cerrado (main).

    Devuelve {origen, cabecera, detalle(solo precio>0), pagos} o None si no existe.
    """
    num = int(_f(numcheque))
    for origen, f_cab, f_det, f_pag in _FUENTES:
        p_cab = os.path.join(base_dir, f_cab)
        if not os.path.exists(p_cab):
            continue
        cab = None
        for r in _abrir(p_cab, encoding):
            if int(_f(r.get("NUMCHEQUE"))) == num:
                cab = dict(r)
                break
        if not cab:
            continue
        folio = cab.get("FOLIO")
        detalle = [dict(r) for r in _abrir(os.path.join(base_dir, f_det), encoding)
                   if r.get("FOLIODET") == folio and _f(r.get("PRECIO")) > 0]
        pagos = [dict(r) for r in _abrir(os.path.join(base_dir, f_pag), encoding)
                 if r.get("FOLIO") == folio]
        return {"origen": origen, "cabecera": cab, "detalle": detalle, "pagos": pagos}
    return None


def leer_ventas_dia(base_dir: str, dia: date, encoding: str) -> list:
    """Lee TODAS las ventas (vigente + cerrado) de un día en UNA pasada por tabla.

    Devuelve [{origen, cabecera, detalle(precio>0), pagos}] sin anuladas.
    """
    ventas = []
    for origen, f_cab, f_det, f_pag in _FUENTES:
        p = os.path.join(base_dir, f_cab)
        if not os.path.exists(p):
            continue
        cabs = {}
        for r in _abrir(p, encoding):
            fec = r.get("FECHA")
            fd = fec.date() if isinstance(fec, datetime) else fec
            # solo ventas con folio de cuenta real (NUMCHEQUE>0), no anuladas.
            # NUMCHEQUE==0 => mesa abierta sin cuenta asignada (no facturable).
            if fd == dia and not r.get("CANCELADO") and int(_f(r.get("NUMCHEQUE"))) > 0:
                cabs[r.get("FOLIO")] = dict(r)
        if not cabs:
            continue
        det_by, pag_by = {}, {}
        for r in _abrir(os.path.join(base_dir, f_det), encoding):
            fo = r.get("FOLIODET")
            if fo in cabs and _f(r.get("PRECIO")) > 0:
                det_by.setdefault(fo, []).append(dict(r))
        for r in _abrir(os.path.join(base_dir, f_pag), encoding):
            fo = r.get("FOLIO")
            if fo in cabs:
                pag_by.setdefault(fo, []).append(dict(r))
        for fo, cab in cabs.items():
            ventas.append({"origen": origen, "cabecera": cab,
                           "detalle": det_by.get(fo, []), "pagos": pag_by.get(fo, [])})
    return ventas


def ventas_del_dia(base_dir: str, dia: date, encoding: str) -> list:
    """NUMCHEQUE de todas las ventas (vigente + cerrado) de un día dado, no anuladas."""
    nums = []
    for _origen, f_cab, _fd, _fp in _FUENTES:
        p = os.path.join(base_dir, f_cab)
        if not os.path.exists(p):
            continue
        for r in _abrir(p, encoding):
            fec = r.get("FECHA")
            fd = fec.date() if isinstance(fec, datetime) else fec
            if fd == dia and not r.get("CANCELADO"):
                nums.append(int(_f(r.get("NUMCHEQUE"))))
    return sorted(set(nums))


# ───────────────────────── nombre de forma de pago ─────────────────────────
def _nombre_pago(codigo: str, fc: dict) -> str:
    for p in fc.get("formas_pago", []):
        if p.get("codigo") == codigo:
            return p.get("nombre") or codigo
    return codigo


# ───────────────────────── construir comprobante SUNAT (Paso 3) ─────────────────────────
def construir_comprobante(venta: dict, productos: dict, fc: dict,
                          cliente_override: dict | None = None) -> dict:
    cab = venta["cabecera"]
    cat = fc["catalogos"]
    fecha = cab.get("FECHA")
    igvp, ipmp = tasa_por_fecha(fecha, fc.get("igv_reglas", []))
    factor = 1 + (igvp + ipmp) / 100
    total = _f(cab.get("TOTAL"))
    anulado = bool(cab.get("CANCELADO"))

    # Tipo y cliente: factura si hay RUC; si no, boleta.
    ov = cliente_override or {}
    if ov.get("ruc"):
        tipo = cat["tipo_factura"]
        cliente = {"tipo_doc": cat["doc_ruc"], "num_doc": ov["ruc"],
                   "nombre": ov.get("nombre", "")}
    else:
        tipo = cat["tipo_boleta"]
        cliente = {"tipo_doc": cat["doc_sin"], "num_doc": ov.get("num_doc", ""),
                   "nombre": ov.get("nombre", "VARIOS")}
    serie = fc["series"]["factura"] if tipo == cat["tipo_factura"] else fc["series"]["boleta"]

    items, base_sum, igv_sum, ipm_sum = [], 0.0, 0.0, 0.0
    for d in venta["detalle"]:
        clave = _txt(d.get("CLAVEPROD"))
        cant = _f(d.get("CANTIDAD")) or 1
        precio_u = _f(d.get("PRECIO"))          # con impuestos
        vu = precio_u / factor if factor else precio_u
        vv = vu * cant
        igv_l = vv * igvp / 100
        ipm_l = vv * ipmp / 100
        base_sum += vv
        igv_sum += igv_l
        ipm_sum += ipm_l
        items.append({
            "codigo": clave,
            "descripcion": (productos.get(clave, {}).get("desc") or f"PRODUCTO {clave}"),
            "cantidad": cant,
            "unidad": cat["unidad_medida"],
            "valor_unitario": _r2(vu),
            "precio_unitario": _r2(precio_u),
            "afectacion_igv": cat["afectacion_igv"],
            "valor_venta": _r2(vv),
            "igv": _r2(igv_l),
            "ipm": _r2(ipm_l),
        })

    gravadas, igv, ipm = _r2(base_sum), _r2(igv_sum), _r2(ipm_sum)
    importe = _r2(gravadas + igv + ipm)
    # cuadrar el centavo de redondeo contra el TOTAL real del POS
    dif = _r2(total - importe)
    if items and abs(dif) <= 0.05:
        igv = _r2(igv + dif)
        importe = _r2(gravadas + igv + ipm)

    pagos = [{"codigo": _txt(p.get("IDFORMADEP")),
              "nombre": _nombre_pago(_txt(p.get("IDFORMADEP")), fc),
              "importe": _r2(_f(p.get("IMPORTE")))} for p in venta["pagos"]]

    return {
        "tipo_comprobante": tipo,
        "serie": serie,
        "correlativo": None,                     # lo asigna el facturador al emitir
        "fecha_emision": fecha.isoformat() if hasattr(fecha, "isoformat") else str(fecha),
        "moneda": fc.get("moneda", "PEN"),
        "numcheque_pos": int(_f(cab.get("NUMCHEQUE"))),
        "origen": venta["origen"],
        "cliente": cliente,
        "items": items,
        "totales": {
            "gravadas": gravadas, "igv": igv, "ipm": ipm,
            "importe_total": importe,
            "tasa_igv": igvp, "tasa_ipm": ipmp,
            "en_letras": num_a_letras(importe),
        },
        "forma_pago": cat["forma_pago_sunat"],
        "medio_pago_interno": pagos,
        "anulado": anulado,
        "ya_facturado": False,
    }


# ───────────────────────── resolver archivos (SMB o local) ─────────────────────────
_TABLAS = ["cheques.dbf", "cheqdet.dbf", "chequespagos.dbf",
           "tempcheques.dbf", "tempcheqdet.dbf", "tempchequespagos.dbf",
           "productos.dbf"]


_MAIN = ["cheques.dbf", "cheqdet.dbf", "chequespagos.dbf", "productos.dbf"]
_TEMP = ["tempcheques.dbf", "tempcheqdet.dbf", "tempchequespagos.dbf"]


def resolver_dir(src: dict, workdir: str) -> str:
    """Devuelve un directorio con los DBF de ventas. Local: la carpeta montada;
    SMB: descarga las tablas a `workdir`."""
    stype = (src.get("source_type") or "smb").lower()
    if stype == "local":
        return src.get("local_dir") or ""
    os.makedirs(workdir, exist_ok=True)
    for t in _TABLAS:
        try:
            dbflib._smb_fetch(src, t, workdir)
        except dbflib.DbfError:
            pass  # alguna temp puede no existir en cierto momento
    return workdir


def resolver_cache(src: dict, cache_dir: str, max_age_main: int = 600) -> str:
    """Como resolver_dir pero con caché: las tablas principales (cheques*, productos)
    se vuelven a bajar solo si faltan o están más viejas que `max_age_main` seg
    (cambian al cerrar turno); las `temp*` (turno vigente) SIEMPRE se refrescan."""
    import time
    stype = (src.get("source_type") or "smb").lower()
    if stype == "local":
        return src.get("local_dir") or ""
    os.makedirs(cache_dir, exist_ok=True)
    now = time.time()
    for t in _MAIN:
        p = os.path.join(cache_dir, t)
        if (not os.path.exists(p)) or (now - os.path.getmtime(p) > max_age_main):
            try:
                dbflib._smb_fetch(src, t, cache_dir)
            except dbflib.DbfError:
                pass
    for t in _TEMP:
        try:
            dbflib._smb_fetch(src, t, cache_dir)
        except dbflib.DbfError:
            pass
    return cache_dir
