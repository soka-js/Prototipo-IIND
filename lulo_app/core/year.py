"""Tu año en Lulo v3: capítulos calculados con los datos canónicos del cliente.

Igual que en v2, un capítulo solo aparece si los datos lo sostienen. La diferencia es que ahora
corre para cualquier cliente de la base y que el «momento de protección» de cada capítulo lo
decide el motor (estado del candidato del ramo), no una regla aparte.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

from . import rules
from .engine import Context, evaluate, upcoming
from .features import compute
from .schema import PAGO_PROTEGIDO
from .store import store
from .text import MONTHS, MONTHS_LONG, cop, date_long, millions, num, plural

THEMES = {"intro": "lime", "dinero": "navy", "ingreso": "ink", "carro": "lime", "viajes": "navy", "gente": "pink",
          "mascotas": "lime", "hogar": "navy", "credito": "navy", "gustos": "ink", "cierre": "lime"}
DISCRETIONARY = {"Supermercados", "Restaurantes", "E-commerce", "Transporte", "Salud", "Otros", "Mascotas", "Hoteles",
                 "Aerolineas"}
CATEGORY_NAME = {"Supermercados": "supermercados", "Restaurantes": "restaurantes", "E-commerce": "compras en línea",
                 "Transporte": "transporte", "Salud": "salud", "Otros": "otros gastos", "Mascotas": "mascotas",
                 "Hoteles": "hoteles", "Aerolineas": "aerolíneas"}


def _months(end: date) -> list[tuple[int, int]]:
    y, m = end.year, end.month
    out = []
    for _ in range(12):
        out.append((y, m))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return list(reversed(out))


def _protect(cand: dict | None, up: list[dict], exp_group: str | None) -> dict | None:
    """Momento de protección del capítulo según el estado que decidió el motor."""
    if cand is None:
        return None
    ramo, st = cand["ramo"], cand["status"]
    base = {"ramo": ramo, "title": cand["title"], "partner": cand["partner"], "price": cand["price"],
            "kind": cand["kind"]}
    if st == "has":
        return {**base, "state": "has", "t": "Ya lo tienes activo", "d": f"{cand['title']}" +
                (f" con {cand['partner']}." if cand["partner"] else ".")}
    if st == "external":
        return {**base, "state": "external", "t": "Lo tienes con otra aseguradora", "d": cand["reason"] + "."}
    nxt = next((u for u in up if u["ramo"] == ramo), None)
    if st in ("weak", "ineligible") and nxt:
        return {**base, "state": "soon", "t": f"Te {'falta' if nxt.get('missing') == 1 else 'faltan'} "
                f"{nxt.get('missing_label', '')} para activarlo",
                "d": f"{nxt['reason']}. Te avisamos el {date_long(nxt['date'], False)}."}
    if st == "ineligible":
        return {**base, "state": "ineligible", "t": "Por ahora no aplica", "d": cand["reason"] + "."}
    if st != "ofrecer":
        return None
    if exp_group == "control":
        return {**base, "state": "control"}
    return {**base, "state": "offer", "ev": cand["ev"]}


def chapters(cid: str, ctx: Context | None = None) -> list[dict]:
    ctx = ctx or Context()
    ctx = ctx.model_copy(update={"mode": "lote"})
    s = store()
    h = s.history(cid)
    as_of = ctx.as_of or s.cutoff
    until = min(as_of, s.cutoff)
    start = until - timedelta(days=rules.LOOKBACK_DAYS)
    ev = evaluate(cid, ctx)
    if ev["outcome"] == "noconsent":
        return []
    cands = {c["ramo"]: c for c in ev["candidates"]}
    up = upcoming(cid, ctx)
    grp = (ev["experiment"] or {}).get("group")
    f = compute(h, as_of, s.cutoff)
    movs = [m for m in h.movements if start < m.date <= until]
    deps = [d for d in h.deposits if start < d.date <= until]
    out = []

    def ch(cid_, name, spec, **kw):
        out.append({"id": cid_, "theme": THEMES[cid_], "name": name, "spec": spec, **kw})

    first = min([m.date for m in movs] + [d.date for d in deps], default=start)
    ch("intro", "Portada",
       "Resume el periodo y la cantidad de movimientos leídos. Invita a recorrer el año como una historia.",
       kicker="Tus últimos 12 meses", stats=[{"big": num(len(movs) + len(deps)), "line": "movimientos en Lulo"}],
       sub=f"De {MONTHS_LONG[first.month - 1]} de {first.year} a {MONTHS_LONG[until.month - 1]} de {until.year}. "
           f"Esto es lo que contaron de ti.", hint="Toca a la derecha para seguir")

    # Tu dinero: lo que entró; si no hubo ingresos en Lulo, lo que se movió.
    months = _months(until)
    inflow, outflow = defaultdict(int), defaultdict(int)
    for m in movs:
        k = (m.date.year, m.date.month)
        if m.amount > 0 and m.category != "Desembolso crédito":
            inflow[k] += m.amount
        elif m.amount < 0:
            outflow[k] -= m.amount
    use_in = sum(inflow.values()) > 0
    series = inflow if use_in else outflow
    mx = max([series[k] for k in months] + [1])
    best = max(months, key=lambda k: series[k])
    hi_from = None
    if use_in and f.income_months and len(f.income_months) < 11:
        y, mo = map(int, f.income_months[-f.income_streak].split("-"))
        hi_from = (y, mo)
    bars = [{"l": MONTHS[mo - 1], "v": round(series[(y, mo)] / mx * 100),
             "hi": ((y, mo) >= hi_from) if hi_from else ((y, mo) == best)} for y, mo in months]
    # La cifra grande cubre los 365 días del periodo; las barras, los 12 meses calendario.
    total = sum(m.amount for m in movs if m.amount > 0 and m.category != "Desembolso crédito") if use_in \
        else -sum(m.amount for m in movs if m.amount < 0)
    if use_in:
        if hi_from:
            before = [inflow[k] for k in months if k < hi_from]
            after = [inflow[k] for k in months if k >= hi_from]
            growth = (sum(after) / len(after)) / (sum(before) / len(before)) - 1 if before and sum(before) else None
            sub = (f"Desde {MONTHS_LONG[hi_from[1] - 1]}, cuando tu nómina empezó a llegar a Lulo, "
                   + (f"lo que recibes al mes subió más de {int(growth * 100) // 10 * 10}%." if growth and growth > 0.1
                      else "tu ingreso llega cada mes."))
        else:
            sub = f"Tu mejor mes fue {MONTHS_LONG[best[1] - 1]}, con {millions(series[best])}."
        line = "llegaron a tu cuenta este año"
    else:
        sub = (f"No recibiste ingresos en Lulo: la usas para pagar y ahorrar. Tu mes de más movimiento fue "
               f"{MONTHS_LONG[best[1] - 1]}.")
        line = "salieron de tu cuenta este año"
    ch("dinero", "Tu dinero", "Capítulo de contexto: lo que entró (o salió) cada mes. No ofrece nada; construye "
       "confianza en que los datos son del cliente.", kicker="Tu dinero",
       stats=[{"big": millions(total), "line": line}], viz={"type": "bars", "items": bars}, sub=sub)

    # Tu ingreso
    if f.income_months:
        full = len(f.income_months) >= 11
        p = _protect(cands["Desempleo"], up, grp)
        ch("ingreso", "Tu ingreso", "El dato son los abonos recurrentes. El momento de protección es el seguro de "
           "desempleo: se ofrece si acredita 6 abonos seguidos (proxy de antigüedad laboral) o se agenda.",
           kicker="Tu ingreso", viz={"type": "dots", "n": f.income_streak},
           stats=[{"big": f"{f.income_streak} de {f.income_streak}", "line": "abonos de tu ingreso llegaron seguidos"}],
           sub=("Lulo fue la cuenta de tu ingreso todo el año, sin un solo mes por fuera." if full else
                f"Desde {MONTHS_LONG[int(f.income_months[-f.income_streak][5:]) - 1]} tu ingreso llega a Lulo."),
           protect=p)
    else:
        occasional = [m for m in movs if m.category == "Ingreso ocasional" and m.amount > 0]
        payers = Counter(m.merchant for m in occasional if m.merchant)
        if len(payers) >= 3:
            ch("ingreso", "Tu trabajo", "Capítulo sin oferta: el ingreso viene de varios pagadores y ninguno es "
               "recurrente. El motor no ofrece desempleo y lo explica.", kicker="Tu trabajo",
               stats=[{"big": str(len(payers)), "line": "pagadores distintos este año"}],
               viz={"type": "chips", "items": [n.removeprefix("Pago ") for n, _ in payers.most_common(5)]},
               sub=f"Recibiste {len(occasional)} pagos. Tus ingresos cambian mes a mes, así que no hay una nómina "
                   f"que proteger: por eso no te ofrecemos ese seguro.")

    # Tu carro
    soat_c = cands["SOAT"]
    if f.tolls_12m >= rules.SOAT_TOLLS_MEDIA or f.soat_expiry:
        stats = [{"big": str(f.tolls_12m), "line": "peajes"}]
        fuel = [m for m in movs if m.category == "Combustible"]
        if fuel:
            stats.append({"big": str(len(fuel)), "line": "tanqueadas"})
        sub = (f"Tu peaje más repetido fue {f.top_toll.split(' · ')[0]}." if f.top_toll else
               f"Pagaste peajes en {len({(m.date.year, m.date.month) for m in movs if m.category == 'Peajes'})} meses distintos.")
        if f.soat_expiry:
            sub += f" Tu SOAT vence el {date_long(f.soat_expiry, False)}."
        ch("carro", "Tu carro", "El dato son los peajes (la base no trae combustible) y el vencimiento del SOAT. "
           "El momento de protección es renovar el SOAT o cotizarlo.", kicker="Tu carro", stats=stats, sub=sub,
           soat={"expiry": f.soat_expiry.isoformat() if f.soat_expiry else None, "days": f.soat_days,
                 "source": f.soat_source}, protect=_protect(soat_c, up, grp))

    # Tus viajes
    vi = cands["Viajes"]
    if vi["strength"] in ("fuerte", "media") or f.travel_12m:
        m = vi["signal"]["metrics"]
        if m.get("pocket_total"):
            stats = [{"big": millions(m["pocket_total"]), "line": f"ahorrados en tu bolsillo «{m.get('pocket_name') or 'Viajes'}»"}]
        else:
            spent = sum(t["amount"] for t in f.travel_12m)
            stats = [{"big": millions(spent), "line": "en vuelos y hoteles"}]
        sub = (plural(len(f.travel_12m), "compra de viaje", "compras de viaje") + " este año"
               + (f"; la última hace {f.travel_12m[-1]['days_ago']} días." if f.travel_12m else ".")
               + (" Parece que se viene un viaje." if vi["strength"] in ("fuerte", "media") else ""))
        ch("viajes", "Tus viajes", "El dato son compras en aerolíneas y hoteles y los abonos a un bolsillo de viajes. "
           "El momento de protección es el seguro de viaje.", kicker="Tus viajes", stats=stats, sub=sub,
           protect=_protect(vi, up, grp))

    # Tu gente
    if f.fixed_months >= rules.VIDA_MIN_MONTHS:
        who = f.fixed_counterparties
        if len(who) == 1:
            line, pt = f"enviados a {who[0]}", f"Que {who[0].split(' · ')[-1]} siga contando contigo"
        elif who:
            line, pt = "para tu familia", "Que tu familia siga contando contigo"
        else:
            line, pt = "enviados a la misma persona", "Que quien depende de ti siga contando contigo"
        p = _protect(cands["Vida"], up, grp)
        if p and p.get("state") == "offer":
            p["t"] = pt
        ch("gente", "Tu gente", "El dato son transferencias fijas a un tercero. El momento de protección es vida "
           "voluntario, que todavía es un producto por negociar.", kicker="Tu gente",
           stats=[{"big": millions(f.fixed_total), "line": line}],
           sub=f"Transferiste en {plural(f.fixed_months, 'mes', 'meses')} distintos. Alguien cuenta contigo.",
           protect=p, concept=True)

    # Tu mascota
    if cands["Mascotas"]["strength"] in ("fuerte", "media"):
        ch("mascotas", "Tu mascota", "El dato son compras en tiendas de mascotas (MCC 5995) y el bolsillo de "
           "mascotas. El momento de protección es el seguro de mascotas.", kicker="Tu mascota",
           stats=[{"big": str(f.pet_spend_12m), "line": "compras para tu mascota"}],
           sub="Se nota que alguien de cuatro patas vive contigo.", protect=_protect(cands["Mascotas"], up, grp))

    # Tu hogar
    if cands["Hogar"]["strength"] in ("fuerte", "media"):
        m = cands["Hogar"]["signal"]["metrics"]
        ch("hogar", "Tu hogar", "El dato son los abonos a un bolsillo de vivienda. El momento de protección es el "
           "seguro de hogar.", kicker="Tu hogar", stats=[{"big": millions(m["pocket_total"]), "line": "ahorrados para tu vivienda"}],
           sub=f"{plural(m['pocket_deposits'], 'abono', 'abonos')} este año.", protect=_protect(cands["Hogar"], up, grp))

    # Tu crédito
    cuotas = [m for m in movs if m.category == "Cuota crédito"]
    if h.client.has_credit:
        has_pp = h.client.holds(PAGO_PROTEGIDO)
        if cuotas:
            stats = [{"big": str(len(cuotas)), "line": "cuotas de Lulo Crédito pagadas a tiempo"}]
        else:
            stats = [{"big": "Activo", "line": "tienes un crédito con Lulo"}]
        sub = ("Y estuvieron protegidas: con pago protegido, si pierdes el empleo se cubren tus cuotas."
               if has_pp else "Tus cuotas no tienen pago protegido.")
        ch("credito", "Tu crédito", "Muestra un beneficio que el cliente ya tiene y no percibe (pago protegido) y "
           "pregunta si lo sabía.", kicker="Tu crédito", stats=stats, sub=sub, ask=PAGO_PROTEGIDO if has_pp else None)

    # Tus favoritos
    disc = [m for m in movs if m.category in DISCRETIONARY and m.amount < 0]
    if disc:
        named = [m for m in disc if m.merchant]
        if named:
            top = Counter(m.merchant for m in named).most_common(3)
            big = {"big": str(top[0][1]), "line": f"compras en {top[0][0]}"}
            items = [{"l": n, "v": c} for n, c in top]
        else:
            top = Counter(m.category for m in disc).most_common(3)
            big = {"big": str(top[0][1]), "line": f"pagos en {CATEGORY_NAME.get(top[0][0], top[0][0].lower())}"}
            items = [{"l": CATEGORY_NAME.get(n, n).capitalize(), "v": c} for n, c in top]
        cat, n = Counter(m.category for m in disc).most_common(1)[0]
        ch("gustos", "Tus favoritos", "Capítulo de contexto: lo que más repite el cliente. Hace que el resumen se "
           "sienta propio y no un folleto de seguros.", kicker="Tus favoritos", stats=[big],
           viz={"type": "rank", "items": items},
           sub=f"Tu categoría favorita fue {CATEGORY_NAME.get(cat, cat.lower())}: {round(n / len(disc) * 100)}% de "
               f"tus pagos del día a día.")

    ch("cierre", "Tu año, protegido", "Cierre: lo que el cliente tiene cubierto, lo que activó en el recorrido y lo "
       "que queda sugerido. Permite compartir el año.", kicker="Tu año, protegido")
    return out
