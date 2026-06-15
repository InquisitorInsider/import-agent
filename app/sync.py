"""Motor de comparación (diff) entre el índice del DBF y los clientes del bot.

Cruce por celular normalizado (N dígitos). Categorías que produce:

  nombre_distinto : el cliente existe en ambos, pero el nombre difiere. El bot
                    suele tener basura ("un cuarto de pollo", "xxx", ".") porque
                    la gente no escribe su nombre. Marcamos `bot_sospechoso`
                    cuando el nombre del bot parece basura, para sugerir corregir
                    con el del DBF.
  falta_direccion : el cliente del bot no tiene dirección y el DBF sí tiene una.
  solo_en_bot     : el bot tiene el cliente (con celular_real) pero el DBF no.
  coincide        : mismo nombre (normalizado). Nada que hacer.

Aplicar correcciones SOLO actualiza clientes que ya existen en el bot.
"""
from __future__ import annotations

import re
import unicodedata

from . import botdb

_WORD = re.compile(r"[a-z0-9ñ]+")
# Palabras típicas de "basura" (pedido en vez de nombre).
_BASURA = {
    "pollo", "pollos", "brasa", "cuarto", "medio", "octavo", "entero", "parrilla",
    "parrillada", "gaseosa", "chicha", "papas", "ensalada", "combo", "delivery",
    "pedido", "porfa", "porfavor", "gracias", "hola", "buenas", "amigo", "amiga",
    "señor", "senor", "señora", "senora", "casero", "casera", "vecino", "cliente",
    "prueba", "test", "asd", "xxx", "aaa", "nn",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return " ".join(_WORD.findall(s.lower()))


def es_sospechoso(nombre: str) -> bool:
    """Heurística: ¿el nombre del bot parece basura en vez de un nombre real?"""
    n = _norm(nombre)
    if not n:
        return True
    palabras = n.split()
    if len(n.replace(" ", "")) < 3:           # demasiado corto
        return True
    if any(p in _BASURA for p in palabras):    # contiene palabras de pedido
        return True
    if not re.search(r"[a-z]", n):             # sin letras (solo números/símbolos)
        return True
    if len(set(n.replace(" ", ""))) <= 2:      # "aaaa", "....", "xxxx"
        return True
    return False


def diff(index_clientes: dict[str, dict], bot_clientes: dict[str, dict]) -> dict:
    nombre_distinto, falta_direccion, solo_en_bot, coincide = [], [], [], []

    for cel, b in bot_clientes.items():
        idx = index_clientes.get(cel)
        if not idx:
            solo_en_bot.append({"celular": cel, "lid": b["lid"],
                                "nombre_bot": b["nombre"]})
            continue
        if _norm(b["nombre"]) != _norm(idx["nombre"]):
            nombre_distinto.append({
                "celular": cel,
                "lid": b["lid"],
                "nombre_bot": b["nombre"],
                "nombre_dbf": idx["nombre"],
                "bot_sospechoso": es_sospechoso(b["nombre"]),
            })
        else:
            coincide.append(cel)
        # dirección: el bot no tiene ninguna y el DBF sí
        if not b["direcciones"] and idx["direcciones"]:
            d0 = idx["direcciones"][0]
            falta_direccion.append({
                "celular": cel,
                "lid": b["lid"],
                "nombre_bot": b["nombre"],
                "calle_dbf": d0.get("calle", ""),
                "referencia_dbf": d0.get("referencia", ""),
            })

    # ordenar: primero los sospechosos (más probable que sean correcciones reales)
    nombre_distinto.sort(key=lambda x: (not x["bot_sospechoso"], x["nombre_bot"]))
    return {
        "resumen": {
            "nombre_distinto": len(nombre_distinto),
            "de_esos_bot_sospechoso": sum(1 for x in nombre_distinto if x["bot_sospechoso"]),
            "falta_direccion": len(falta_direccion),
            "solo_en_bot": len(solo_en_bot),
            "coincide": len(coincide),
            "clientes_bot_cruzables": len(bot_clientes),
        },
        "nombre_distinto": nombre_distinto,
        "falta_direccion": falta_direccion,
        "solo_en_bot": solo_en_bot,
    }


def aplicar(bot_db_path: str, index_clientes: dict[str, dict],
            acciones: list[dict]) -> dict:
    """Aplica correcciones al bot. Cada acción:
        {"celular": "9...", "lid": "...", "tipo": "nombre"|"direccion"}
    - nombre   : pone en el bot el nombre del DBF.
    - direccion: agrega al bot la primera dirección del DBF.
    """
    hechas = {"nombre": 0, "direccion": 0, "errores": []}
    for a in acciones:
        cel = a.get("celular")
        lid = a.get("lid")
        idx = index_clientes.get(cel)
        if not idx or not lid:
            hechas["errores"].append(cel)
            continue
        try:
            if a.get("tipo") == "nombre":
                botdb.actualizar_nombre(bot_db_path, lid, idx["nombre"])
                hechas["nombre"] += 1
            elif a.get("tipo") == "direccion" and idx["direcciones"]:
                d0 = idx["direcciones"][0]
                botdb.agregar_direccion(bot_db_path, lid, d0.get("calle", ""),
                                        d0.get("referencia", ""))
                hechas["direccion"] += 1
        except Exception as e:  # noqa: BLE001
            hechas["errores"].append(f"{cel}: {e}")
    return hechas
