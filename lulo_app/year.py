"""Tu año en Lulo: capítulos armados con un año de movimientos y las señales detectadas.

Cada capítulo sale de una regla sobre los movimientos del cliente, así que con
datos reales se recalcula sin cambiar el diseño. Un capítulo solo aparece si la
señal que lo sostiene existe: quien no tiene carro no ve «Tu carro».
"""

from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache

from . import fmt
from .signals import for_persona as signals_for
from .simulator import MONTHS, PERIOD_START, TODAY, get, months_in_period

THEMES = {"intro": "lime", "dinero": "navy", "ingreso": "ink", "carro": "lime", "viajes": "navy",
          "gente": "pink", "credito": "navy", "gustos": "ink", "cierre": "lime"}
DISCRETIONARY = {"mercado", "cafe", "domicilios", "restaurantes", "movilidad", "compras", "entretenimiento", "salud"}


def _chapter(cid: str, name: str, spec: str, **kw) -> dict:
    return {"id": cid, "theme": THEMES[cid], "name": name, "spec": spec, **kw}


def _monthly_income(txs: list[dict]) -> list[tuple[int, int, int]]:
    by = defaultdict(int)
    for t in txs:
        if t["a"] > 0 and t["cat"] != "desembolso":
            by[t["date"][:7]] += t["a"]
    return [(y, m, by.get(f"{y}-{m:02d}", 0)) for y, m in months_in_period()]


@lru_cache(maxsize=None)
def chapters(persona_id: str) -> list[dict]:
    p = get(persona_id)
    sig = signals_for(persona_id)
    txs = p.txs
    out = []

    out.append(_chapter(
        "intro", "Portada",
        "La portada resume el periodo y la cantidad de movimientos leídos. Invita a recorrer el año como una historia.",
        kicker="Tus últimos 12 meses",
        stats=[{"big": fmt.num(len(txs)), "line": "movimientos en Lulo"}],
        sub=f"De {fmt.MONTHS_LONG[PERIOD_START.month - 1]} de {PERIOD_START.year} a "
            f"{fmt.MONTHS_LONG[TODAY.month - 1]} de {TODAY.year}. Esto es lo que contaron de ti.",
        hint="Toca a la derecha para seguir"))

    # Tu dinero
    monthly = _monthly_income(txs)
    total_in = sum(v for *_, v in monthly)
    nom = sig["nomina"]
    hi_from = None
    if nom["detected"] and not nom["metrics"]["full_period"]:
        since = fmt.d(nom["metrics"]["since_iso"])
        hi_from = (since.year, since.month)
        before = [v for y, m, v in monthly if (y, m) < hi_from]
        after = [v for y, m, v in monthly if (y, m) >= hi_from]
        growth = (sum(after) / len(after)) / (sum(before) / len(before)) - 1
        pct = int(growth * 100) // 10 * 10
        sub = (f"Desde {nom['metrics']['since']}, cuando tu nómina empezó a llegar a Lulo, "
               f"lo que recibes al mes subió más de {pct}%.")
    else:
        best = max(monthly, key=lambda x: x[2])
        low = min(monthly, key=lambda x: x[2])
        if nom["detected"]:
            sub = (f"Tu nómina llegó a Lulo todo el año. Tu mejor mes fue {fmt.month_long(best[0], best[1])}, "
                   f"con la prima: {fmt.millions(best[2])}.")
        else:
            sub = (f"Tu mejor mes fue {fmt.month_long(best[0], best[1])} con {fmt.millions(best[2])}"
                   + (f"; en {fmt.month_long(low[0], low[1])} no entró ningún pago." if low[2] == 0 else
                      f"; el más bajo, {fmt.month_long(low[0], low[1])} con {fmt.millions(low[2])}.")
                   + " Así se ve un ingreso independiente.")
    mx = max(v for *_, v in monthly) or 1
    best_key = max(monthly, key=lambda x: x[2])[:2]
    bars = [{"l": MONTHS[m - 1], "v": round(v / mx * 100),
             "hi": (hi_from is not None and (y, m) >= hi_from) or (hi_from is None and (y, m) == best_key)}
            for y, m, v in monthly]
    out.append(_chapter(
        "dinero", "Tu dinero",
        "Capítulo de contexto: muestra lo que entró a la cuenta cada mes. No ofrece nada, construye confianza en "
        "que los datos son del cliente.",
        kicker="Tu dinero", stats=[{"big": fmt.millions(total_in), "line": "llegaron a tu cuenta este año"}],
        viz={"type": "bars", "items": bars}, sub=sub))

    # Tu ingreso / Tu trabajo
    if nom["detected"]:
        m = nom["metrics"]
        out.append(_chapter(
            "ingreso", "Tu ingreso",
            "El dato son los abonos del mismo originador. El momento de protección ofrece el seguro de nómina de "
            "Chubb, o confirma que ya lo tiene.",
            kicker="Tu ingreso", viz={"type": "dots", "n": m["streak"]},
            stats=[{"big": f"{m['streak']} de {m['streak']}", "line": f"nóminas de {m['employer']} llegaron a tiempo"}],
            sub=(f"Desde {m['since']} Lulo es la cuenta donde recibes tu sueldo." if not m["full_period"]
                 else "Lulo fue la cuenta de tu sueldo todo el año, sin un solo retraso."),
            protect={"key": "nomina", "t": "Si un mes no llega, que no se note",
                     "d": "Seguro de nómina con Chubb: hasta 3 meses de tu ingreso si pierdes el empleo. "
                          "Desde $14.500 al mes."}))
    elif nom["strength"] == "débil":
        m = nom["metrics"]
        out.append(_chapter(
            "ingreso", "Tu trabajo",
            "Capítulo sin oferta: el ingreso viene de varios clientes y ninguno es nómina. El motor no ofrece seguro "
            "de nómina y lo explica, para que el cliente entienda por qué.",
            kicker="Tu trabajo",
            stats=[{"big": str(m["sources"]), "line": "clientes te pagaron este año"}],
            viz={"type": "chips", "items": m["clients"][:5]},
            sub=f"Recibiste {m['payments']} pagos. Tus ingresos cambian mes a mes, así que no hay una nómina que "
                f"proteger: por eso no te ofrecemos ese seguro."))

    # Tu carro
    veh = sig["vehiculo"]
    if veh["detected"]:
        m = veh["metrics"]
        out.append(_chapter(
            "carro", "Tu carro",
            "El dato son peajes, combustible y parqueaderos. El momento de protección conecta con el recordatorio "
            "de vencimiento: renovar el SOAT antes de que venza.",
            kicker="Tu carro",
            stats=[{"big": str(m["tolls"]), "line": "peajes"}, {"big": str(m["fuel"]), "line": "tanqueadas"}],
            sub=f"{fmt.about_millions(m['fuel_total'])} en combustible. Tu peaje más repetido fue {m['top_toll']}"
                + (f", en la {m['top_route']}." if m["top_route"].startswith(("Autopista", "Vía", "Calle")) else
                   f", rumbo a {m['top_route']}." if m["top_route"] else "."),
            soat=bool(p.car)))

    # Tus viajes
    tr = sig["viaje"]
    if tr["detected"]:
        m = tr["metrics"]
        if m["deposits"]:
            stats = [{"big": fmt.millions(m["total"]), "line": f"ahorrados en tu cajita «{m['cajita']}»"}]
            sub = f"{m['deposits']} abonos"
            if m["flights"]:
                sub += f" y un tiquete en {m['flights'][0]['n'].split(' · ')[0]}: el viaje ya tiene fecha."
            else:
                amounts = {-t["a"] for t in txs if t["cat"] == "cajitas" and t.get("tag") == "viaje"}
                sub += (f" de {fmt.cop(amounts.pop())}" if len(amounts) == 1 else "") + ". Parece que se viene un viaje."
        else:
            f = m["flights"][0]
            stats = [{"big": fmt.millions(f["a"]), "line": f"en tiquetes con {f['n'].split(' · ')[0]}"}]
            sub = "Se viene un viaje."
        out.append(_chapter(
            "viajes", "Tus viajes",
            "El dato son los abonos a una cajita de viaje y las compras de tiquetes. El momento de protección "
            "ofrece seguro de viaje con IGS.",
            kicker="Tus viajes", stats=stats, sub=sub,
            protect={"key": "viaje", "t": "Que el viaje sea solo de buenos recuerdos",
                     "d": "Seguro de viaje con IGS: asistencia médica en el exterior hasta USD 30.000. $18.900 por viaje."}))

    # Tu gente
    dep = sig["vida"]
    if dep["detected"]:
        bens = dep["metrics"]["beneficiaries"]
        if len(bens) == 1:
            b = bens[0]
            line = f"enviados a {b['name']}"
            sub = f"Le transferiste todos los meses desde {b['since']}, sin fallar uno. Alguien cuenta contigo."
            pt = f"Que {b['name'].split(' · ')[-1]} siga contando contigo"
        else:
            line = "para tu familia"
            sub = ("; ".join(f"{b['name']}: {fmt.millions(b['total'])}" for b in bens)
                   + ". Hay personas que cuentan contigo.")
            pt = "Que tu familia siga contando contigo"
        out.append(_chapter(
            "gente", "Tu gente",
            "El dato son transferencias o pagos fijos a un mismo tercero. El momento de protección ofrece vida "
            "voluntario, que todavía es un producto por negociar.",
            kicker="Tu gente", stats=[{"big": fmt.millions(dep["metrics"]["total"]), "line": line}], sub=sub,
            protect={"key": "vida", "t": pt, "concept": True,
                     "d": "Vida voluntario con AXA Colpatria: tú eliges a quién proteger. Desde $22.000 al mes."}))

    # Tu crédito
    cr = sig["credito"]
    if cr["detected"]:
        m = cr["metrics"]
        out.append(_chapter(
            "credito", "Tu crédito",
            "Muestra un beneficio que el cliente ya tiene y no percibe: el pago protegido de su crédito. "
            "Pregunta si lo sabía.",
            kicker="Tu crédito",
            stats=[{"big": f"{m['paid']} de {m['cuotas']}", "line": "cuotas de Lulo Crédito pagadas a tiempo"}],
            sub=(f"Y estuvieron protegidas: con pago protegido de SBS, si pierdes el empleo se cubren hasta 6 cuotas "
                 f"de {fmt.cop(m['cuota'])}." if m["protected"] else "Tus cuotas no tienen pago protegido."),
            ask="pago" if m["protected"] else None))

    # Tus favoritos
    disc = [t for t in txs if t["cat"] in DISCRETIONARY]
    top = Counter(t["n"] for t in disc).most_common(3)
    cats = Counter(t["c"] for t in disc)
    cat_name, cat_n = cats.most_common(1)[0]
    out.append(_chapter(
        "gustos", "Tus favoritos",
        "Capítulo de contexto y de juego: lo que más repite el cliente. Hace que el resumen se sienta propio y "
        "no un folleto de seguros.",
        kicker="Tus favoritos", stats=[{"big": str(top[0][1]), "line": f"compras en {top[0][0]}"}],
        viz={"type": "rank", "items": [{"l": n, "v": c} for n, c in top]},
        sub=f"Tu categoría favorita fue {cat_name.lower()}: {round(cat_n / len(disc) * 100)}% de tus compras del día a día."))

    out.append(_chapter(
        "cierre", "Tu año, protegido",
        "Cierre del resumen: lo que el cliente tiene cubierto, lo que activó en el recorrido y lo que queda "
        "sugerido. Permite compartir el año.",
        kicker="Tu año, protegido"))
    return out
