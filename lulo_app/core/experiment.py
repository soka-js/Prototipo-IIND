"""Grupo de control y política de decisión, deterministas: el mismo cliente cae siempre en el mismo grupo.

La asignación usa un hash del id con una sal fija; no depende del orden ni de la fecha.
  bucket < CONTROL_PCT                              control: se registra la decisión, no se muestra
  CONTROL_PCT ≤ bucket < CONTROL_PCT + EXPLORE_PCT  tratamiento que explora (muestreo de Thompson, v2.0)
  el resto                                          tratamiento que explota (la mejor estimación)
Los personajes de demostración no se sortean: el panel decide si se ven como control o explorando.
"""

from __future__ import annotations

import hashlib

from . import rules


def bucket(client_id: str, salt: str = rules.CONTROL_SALT) -> int:
    return int(hashlib.sha256(f"{salt}:{client_id}".encode()).hexdigest()[:8], 16) % 100


def group(client_id: str, source: str, override: bool | None = None, policy: str | None = None) -> dict:
    if override is not None:
        g = "control" if override else "tratamiento"
        return {"group": g, "bucket": None, "via": "panel", "policy": None if override else (policy or "explotar")}
    if source == "persona":
        return {"group": "tratamiento", "bucket": None, "via": "personaje de demostración (no se sortea)",
                "policy": policy or "explotar"}
    b = bucket(client_id)
    if b < rules.CONTROL_PCT:
        return {"group": "control", "bucket": b, "policy": None,
                "via": f"hash sha256 con sal «{rules.CONTROL_SALT}» mod 100 < {rules.CONTROL_PCT}"}
    explore = b < rules.CONTROL_PCT + rules.EXPLORE_PCT
    return {"group": "tratamiento", "bucket": b, "policy": policy or ("explorar" if explore else "explotar"),
            "via": f"hash sha256 con sal «{rules.CONTROL_SALT}» mod 100 = {b}"
                   + (f" (exploración: {rules.CONTROL_PCT} a {rules.CONTROL_PCT + rules.EXPLORE_PCT - 1})" if explore else "")}
