"""Grupo de control determinista: el mismo cliente cae siempre en el mismo grupo.

La asignación usa un hash del id con una sal fija; no depende del orden ni de la fecha.
Los personajes de demostración no se sortean: el panel decide si se ven como control.
"""

from __future__ import annotations

import hashlib

from . import rules


def bucket(client_id: str, salt: str = rules.CONTROL_SALT) -> int:
    return int(hashlib.sha256(f"{salt}:{client_id}".encode()).hexdigest()[:8], 16) % 100


def group(client_id: str, source: str, override: bool | None = None) -> dict:
    if override is not None:
        return {"group": "control" if override else "tratamiento", "bucket": None, "via": "panel"}
    if source == "persona":
        return {"group": "tratamiento", "bucket": None, "via": "personaje de demostración (no se sortea)"}
    b = bucket(client_id)
    return {"group": "control" if b < rules.CONTROL_PCT else "tratamiento", "bucket": b,
            "via": f"hash sha256 con sal «{rules.CONTROL_SALT}» mod 100 < {rules.CONTROL_PCT}"}
