"""Formatos en español de Colombia para los textos del motor."""

from __future__ import annotations

from datetime import date

MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MONTHS_LONG = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
               "noviembre", "diciembre"]


def num(n: float) -> str:
    return f"{round(n):,}".replace(",", ".")


def cop(n: float) -> str:
    return ("−" if n < 0 else "") + "$" + num(abs(n))


def millions(n: float) -> str:
    txt = f"{abs(n) / 1_000_000:.1f}".removesuffix(".0")
    return "$" + txt.replace(".", ",") + " M"


def pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:.{digits}f}".replace(".", ",") + " %"


def d(x: str | date) -> date:
    return x if isinstance(x, date) else date.fromisoformat(x)


def date_long(x: str | date, year: bool = True) -> str:
    v = d(x)
    return f"{v.day} de {MONTHS_LONG[v.month - 1]}" + (f" de {v.year}" if year else "")


def date_short(x: str | date) -> str:
    v = d(x)
    return f"{v.day} {MONTHS[v.month - 1]}"


def plural(n: int, one: str, many: str) -> str:
    return f"{num(n)} {one if n == 1 else many}"
