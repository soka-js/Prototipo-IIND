"""Formatos en español de Colombia para cifras y fechas."""

from __future__ import annotations

from datetime import date

from .simulator import MONTHS, MONTHS_LONG


def num(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def cop(n: int) -> str:
    return ("−" if n < 0 else "") + "$" + num(abs(int(n)))


def millions(n: int) -> str:
    """$33 M, $1,2 M, $19,5 M."""
    txt = f"{abs(n) / 1_000_000:.1f}".removesuffix(".0")
    return "$" + txt.replace(".", ",") + " M"


def about_millions(n: int) -> str:
    """'Casi $3 millones' o '$6,2 millones'."""
    m = n / 1_000_000
    nxt = int(m) + 1
    if nxt - m <= 0.1:
        return f"Casi ${nxt} millones"
    return f"${m:.1f} millones".replace(".", ",")


def d(iso: str | date) -> date:
    return iso if isinstance(iso, date) else date.fromisoformat(iso)


def date_long(iso: str | date, year: bool = True) -> str:
    x = d(iso)
    out = f"{x.day} de {MONTHS_LONG[x.month - 1]}"
    return out + (f" de {x.year}" if year else "")


def date_short(iso: str | date) -> str:
    x = d(iso)
    return f"{x.day} {MONTHS[x.month - 1]}"


def month_long(y: int, m: int) -> str:
    return MONTHS_LONG[m - 1]


def ordinal(n: int) -> str:
    words = {1: "primer", 2: "segundo", 3: "tercer", 4: "cuarto", 5: "quinto", 6: "sexto", 7: "séptimo",
             8: "octavo", 9: "noveno", 10: "décimo", 11: "undécimo", 12: "duodécimo"}
    return words.get(n, f"{n}.º")


def plural(n: int, one: str, many: str) -> str:
    return f"{num(n)} {one if n == 1 else many}"
