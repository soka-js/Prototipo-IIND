"""Núcleo de probabilidad del motor bayesiano: Python puro, determinista y sin dependencias.

Lo usan igual el entrenamiento (scripts/train_motor.py, scripts/laboratorio.py) y la producción (Vercel no
instala numpy ni scikit-learn). Cada función tiene la fórmula en su documentación para que se pueda revisar
contra la referencia.

Piezas:
  · normal estándar: phi (densidad), Phi (acumulada), Phi_inv (cuantil)
  · Beta: lbeta, digamma, trigamma, betainc (acumulada regularizada) y beta_quantile
  · beta_binomial_eb: Beta-Binomial jerárquico con Bayes empírico (Gelman et al., BDA3, cap. 5)
  · posterior_rejilla / jerarquico_rejilla: posterior exacta en una rejilla para un parámetro y su versión
    jerárquica (efecto por grupo que se encoge hacia el promedio de los grupos)
  · Creencias: regresión probit bayesiana con actualización en línea (ADF), como AdPredictor
    (Graepel et al., 2010, «Web-Scale Bayesian Click-Through Rate Prediction»)
  · rng: generador aleatorio con semilla derivada de un texto (la misma decisión siempre da el mismo sorteo)
"""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from statistics import NormalDist

_N = NormalDist()
SQRT2PI = math.sqrt(2 * math.pi)


# --------------------------------------------------------------------------- normal estándar
def phi(x: float) -> float:
    """Densidad de la normal estándar."""
    return math.exp(-0.5 * x * x) / SQRT2PI


def Phi(x: float) -> float:
    """Acumulada de la normal estándar: Φ(x) = ½·erfc(−x/√2)."""
    return 0.5 * math.erfc(-x / math.sqrt(2))


def Phi_inv(p: float) -> float:
    """Cuantil de la normal estándar (algoritmo AS241 de Wichura, vía statistics.NormalDist)."""
    p = min(max(p, 1e-12), 1 - 1e-12)
    return _N.inv_cdf(p)


def mills(t: float) -> float:
    """v(t) = φ(t)/Φ(t), estable también para t muy negativo (razón de Mills inversa)."""
    if t > -8:
        return phi(t) / Phi(t)
    t2 = t * t
    return -t / (1 - 1 / t2 + 3 / (t2 * t2))


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x)) if x >= 0 else math.exp(x) / (1 + math.exp(x))


def logit(p: float) -> float:
    p = min(max(p, 1e-12), 1 - 1e-12)
    return math.log(p / (1 - p))


# --------------------------------------------------------------------------- funciones Beta
def lbeta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def digamma(x: float) -> float:
    """ψ(x) con recurrencia ψ(x) = ψ(x+1) − 1/x y serie asintótica para x ≥ 10."""
    r = 0.0
    while x < 10:
        r -= 1 / x
        x += 1
    f = 1 / (x * x)
    return r + math.log(x) - 0.5 / x - f * (1 / 12 - f * (1 / 120 - f * (1 / 252 - f * (1 / 240 - f / 132))))


def trigamma(x: float) -> float:
    """ψ₁(x) con recurrencia ψ₁(x) = ψ₁(x+1) + 1/x² y serie asintótica para x ≥ 10."""
    r = 0.0
    while x < 10:
        r += 1 / (x * x)
        x += 1
    f = 1 / (x * x)
    return r + 1 / x + f / 2 + f / x * (1 / 6 - f * (1 / 30 - f * (1 / 42 - f / 30)))


def _betacf(a: float, b: float, x: float) -> float:
    """Fracción continua de la Beta incompleta (Numerical Recipes, betacf)."""
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c
        c = c if abs(c) > 1e-300 else 1e-300
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c
        c = c if abs(c) > 1e-300 else 1e-300
        de = d * c
        h *= de
        if abs(de - 1) < 1e-14:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Acumulada de la Beta(a, b) en x (Beta incompleta regularizada I_x(a, b))."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lf = a * math.log(x) + b * math.log1p(-x) - lbeta(a, b)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lf) * _betacf(a, b, x) / a
    return 1 - math.exp(lf) * _betacf(b, a, 1 - x) / b


def beta_quantile(a: float, b: float, q: float) -> float:
    """Cuantil de la Beta(a, b) por bisección sobre betainc."""
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if betainc(a, b, mid) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def beta_resumen(a: float, b: float) -> dict:
    """Media, desviación e intervalo creíble al 90 % de una Beta(a, b); media y varianza del logit."""
    m = a / (a + b)
    return {"a": a, "b": b, "media": m, "sd": math.sqrt(a * b / ((a + b) ** 2 * (a + b + 1))),
            "ic90": [beta_quantile(a, b, 0.05), beta_quantile(a, b, 0.95)],
            "logit_media": digamma(a) - digamma(b), "logit_var": trigamma(a) + trigamma(b)}


# --------------------------------------------------------------------------- Beta-Binomial jerárquico
def _bb_loglik(rows: list[tuple[int, int]], mu: float, kappa: float) -> float:
    a, b = mu * kappa, (1 - mu) * kappa
    base = lbeta(a, b)
    return sum(lbeta(y + a, n - y + b) - base for y, n in rows)


def beta_binomial_eb(rows: list[tuple[int, int]]) -> dict:
    """Bayes empírico para y_i ~ Binomial(n_i, p_i), p_i ~ Beta(μκ, (1−μ)κ).

    μ es la tasa promedio de los grupos y κ la «concentración»: κ grande = los grupos se parecen mucho
    (la evidencia de cada uno se encoge fuerte hacia μ); κ pequeño = cada grupo es distinto. Se maximiza la
    verosimilitud marginal Σ log B(y_i + a, n_i − y_i + b) − log B(a, b) en una rejilla (μ, log κ) que se
    refina tres veces alrededor del máximo. Determinista.
    """
    rates = [y / n for y, n in rows]
    lo_mu, hi_mu = max(min(rates) / 3, 1e-4), min(max(rates) * 3, 0.999)
    lo_k, hi_k = math.log(1.0), math.log(1e5)
    best = None
    for _ in range(4):
        mus = [lo_mu + (hi_mu - lo_mu) * i / 60 for i in range(61)]
        ks = [lo_k + (hi_k - lo_k) * j / 60 for j in range(61)]
        for mu in mus:
            for lk in ks:
                ll = _bb_loglik(rows, mu, math.exp(lk))
                if best is None or ll > best[0]:
                    best = (ll, mu, lk)
        _, mu0, lk0 = best
        dmu, dk = (hi_mu - lo_mu) / 10, (hi_k - lo_k) / 10
        lo_mu, hi_mu = max(mu0 - dmu, 1e-4), min(mu0 + dmu, 0.999)
        lo_k, hi_k = max(lk0 - dk, 0.0), min(lk0 + dk, math.log(1e5))
    ll, mu, lk = best
    kappa = math.exp(lk)
    return {"mu": mu, "kappa": kappa, "a": mu * kappa, "b": (1 - mu) * kappa, "loglik": ll,
            "sin_heterogeneidad": kappa > 0.99e5}


def _beta_momentos(m: float, v: float) -> tuple[float, float]:
    """Beta(a, b) con media m y varianza v (método de momentos)."""
    k = m * (1 - m) / v - 1
    return m * k, (1 - m) * k


def beta_binomial_bayes(rows: list[tuple[int, int]], n_mu: int = 121, n_k: int = 121) -> dict:
    """Beta-Binomial jerárquico con Bayes completo en rejilla (Gelman et al., BDA3, sección 5.3).

    y_i ~ Binomial(n_i, p_i), p_i ~ Beta(μκ, (1−μ)κ), con la previa no informativa del libro,
    p(μ, κ) ∝ κ^(−3/2) (equivale a p(a, b) ∝ (a + b)^(−5/2)). Se integra sobre (μ, log κ) en una rejilla:
    así la duda sobre cuánto se parecen los grupos entra al resultado (Bayes empírico la ignora).
    Devuelve la posterior de cada grupo y la predictiva de un grupo nuevo (sin datos), como mezclas de
    Betas resumidas por su media, desviación e intervalo al 90 % (Beta con los mismos momentos).
    """
    eb = beta_binomial_eb(rows)
    rates = [y / n for y, n in rows]
    mus = rejilla(max(min(rates) / 3, 1e-4), min(max(rates) * 3, 0.999), n_mu)
    lks = rejilla(0.0, math.log(1e5), n_k)
    hyp = []
    for mu in mus:
        for lk in lks:
            k = math.exp(lk)
            # p(μ, log κ) ∝ κ^(−3/2) · κ (jacobiano de κ → log κ)
            hyp.append((_bb_loglik(rows, mu, k) - 0.5 * lk, mu, k))
    norm = _logsumexp([h[0] for h in hyp])
    w = [(math.exp(h[0] - norm), h[1], h[2]) for h in hyp]
    w = [t for t in w if t[0] > 1e-10]
    tot = sum(t[0] for t in w)

    def mezcla(y: int, n: int) -> dict:
        m1 = m2 = 0.0
        for wi, mu, k in w:
            a, b = mu * k + y, (1 - mu) * k + n - y
            m = a / (a + b)
            m1 += wi * m
            m2 += wi * (m * m + a * b / ((a + b) ** 2 * (a + b + 1)))
        m1, m2 = m1 / tot, m2 / tot
        var = max(m2 - m1 * m1, 1e-12)
        a, b = _beta_momentos(m1, var)
        return {**beta_resumen(a, b), "media": m1, "sd": math.sqrt(var)}

    mu_m = sum(wi * mu for wi, mu, _ in w) / tot
    lk_m = sum(wi * math.log(k) for wi, _, k in w) / tot
    return {"grupos": [mezcla(y, n) for y, n in rows], "nuevo": mezcla(0, 0), "mu": mu_m,
            "kappa_mediana_geom": math.exp(lk_m), "eb": eb}


# --------------------------------------------------------------------------- posterior en rejilla
def rejilla(lo: float, hi: float, n: int) -> list[float]:
    return [lo + (hi - lo) * i / (n - 1) for i in range(n)]


def _lognorm(x: float, m: float, s: float) -> float:
    return -0.5 * ((x - m) / s) ** 2 - math.log(s * SQRT2PI)


def _logsumexp(v: list[float]) -> float:
    m = max(v)
    return m + math.log(sum(math.exp(x - m) for x in v))


def resumen_rejilla(grid: list[float], w: list[float]) -> dict:
    """Media, desviación, cuantiles 5 % y 95 % y P(θ > 0) de una distribución discreta en la rejilla."""
    m = sum(g * p for g, p in zip(grid, w))
    sd = math.sqrt(max(sum((g - m) ** 2 * p for g, p in zip(grid, w)), 0.0))
    acc, q05, q95 = 0.0, grid[0], grid[-1]
    got05 = False
    for g, p in zip(grid, w):
        acc += p
        if not got05 and acc >= 0.05:
            q05, got05 = g, True
        if acc >= 0.95:
            q95 = g
            break
    return {"media": m, "sd": sd, "q05": q05, "q95": q95, "p_positivo": sum(p for g, p in zip(grid, w) if g > 0)}


def jerarquico_rejilla(logliks: dict[str, list[float]], grid: list[float], *, mu0: float = 0.0, s_mu: float = 1.0,
                       tau_escala: float = 0.5, mus: list[float] | None = None,
                       taus: list[float] | None = None) -> dict:
    """Modelo jerárquico exacto por rejilla: θ_g ~ N(μ, τ²), μ ~ N(mu0, s_mu²), τ ~ media normal(tau_escala).

    `logliks[g]` es la log-verosimilitud del grupo g evaluada en cada punto de `grid` (lista vacía = el grupo
    no tiene datos y su posterior es la predictiva del promedio). Se integra sobre (μ, τ) en una rejilla, sin
    simulación: el resultado es exacto salvo por el paso de las rejillas y no depende de semillas.
    Devuelve, por grupo, la posterior de θ_g en `grid`, y la posterior de μ y τ.
    """
    mus = mus or rejilla(-1.5, 1.5, 61)
    taus = taus or rejilla(0.02, 1.5, 38)
    dg = grid[1] - grid[0]
    groups = list(logliks)
    hyp = []                                   # (log peso, μ, τ, {g: log prior normalizado por punto})
    for mu in mus:
        for tau in taus:
            lp = _lognorm(mu, mu0, s_mu) + _lognorm(tau, 0.0, tau_escala)
            lprior = [_lognorm(t, mu, tau) + math.log(dg) for t in grid]
            norm = _logsumexp(lprior)
            lprior = [x - norm for x in lprior]          # prior discretizado que suma 1 en la rejilla
            per = {}
            for g in groups:
                ll = logliks[g]
                if ll:
                    lm = _logsumexp([a + b for a, b in zip(ll, lprior)])
                    lp += lm
                per[g] = lm if ll else 0.0
            hyp.append((lp, mu, tau, lprior, per))
    norm = _logsumexp([h[0] for h in hyp])
    weights = [math.exp(h[0] - norm) for h in hyp]
    out_groups = {}
    for g in groups:
        ll = logliks[g]
        post = [0.0] * len(grid)
        for w, (_, _, _, lprior, per) in zip(weights, hyp):
            if w < 1e-12:
                continue
            if ll:
                lm = per[g]
                for i in range(len(grid)):
                    post[i] += w * math.exp(ll[i] + lprior[i] - lm)
            else:
                for i in range(len(grid)):
                    post[i] += w * math.exp(lprior[i])
        s = sum(post)
        out_groups[g] = resumen_rejilla(grid, [p / s for p in post])
    mu_w: dict[float, float] = {}
    tau_w: dict[float, float] = {}
    for w, (_, mu, tau, _, _) in zip(weights, hyp):
        mu_w[mu] = mu_w.get(mu, 0.0) + w
        tau_w[tau] = tau_w.get(tau, 0.0) + w
    return {"grupos": out_groups, "mu": resumen_rejilla(mus, [mu_w[m] for m in mus]),
            "tau": resumen_rejilla(taus, [tau_w[t] for t in taus])}


# --------------------------------------------------------------------------- probit bayesiano en línea (ADF)
@dataclass
class Creencias:
    """Creencia gaussiana independiente sobre cada peso: w_k ~ N(media_k, var_k).

    Probabilidad de respuesta positiva: P(y = 1 | x) = Φ(Σ_k x_k·w_k). Con las creencias, la predictiva es
    Φ(m / √(1 + v)), con m = Σ x_k·media_k y v = Σ x_k²·var_k (la duda sobre los pesos aplana la predicción).

    Cada respuesta actualiza en una sola pasada (filtrado de densidad supuesta, ADF), como AdPredictor:
        s² = 1 + v,  z = t·m/s,  t = ±1
        media_k ← media_k + t·x_k·var_k/s · ψ(z)               ψ(z) = φ(z)/Φ(z)
        var_k   ← var_k · (1 − x_k²·var_k/s² · ψ(z)·(ψ(z) + z))
    Un peso que nunca aparece en una respuesta conserva su creencia previa: una variable nueva empieza en
    «no sé» (media 0) y no mueve ninguna decisión hasta que los datos digan algo.
    """

    medias: dict[str, float] = field(default_factory=dict)
    varianzas: dict[str, float] = field(default_factory=dict)
    # Creencia previa de un peso que todavía no se ha actualizado: función nombre → (media, desviación).
    default: Callable[[str], tuple[float, float]] = lambda k: (0.0, 0.0)

    def get(self, k: str) -> tuple[float, float]:
        if k in self.medias:
            return self.medias[k], self.varianzas[k]
        m, s = self.default(k)
        return m, s * s

    def copia(self) -> "Creencias":
        return Creencias(dict(self.medias), dict(self.varianzas), self.default)

    def lineal(self, x: dict[str, float]) -> tuple[float, float]:
        m = v = 0.0
        for k, xk in x.items():
            mk, vk = self.get(k)
            m += xk * mk
            v += xk * xk * vk
        return m, v

    def predictiva(self, x: dict[str, float]) -> float:
        m, v = self.lineal(x)
        return Phi(m / math.sqrt(1 + v))

    def actualizar(self, x: dict[str, float], y: int, solo: set[str] | None = None) -> None:
        """Una respuesta (y = 1 aceptó, 0 no). `solo`: actualiza únicamente esos pesos; la duda de los demás
        sigue entrando en s² (así una respuesta no se le atribuye entera a un solo peso)."""
        t = 1.0 if y else -1.0
        m, v = self.lineal(x)
        s2 = 1 + v
        s = math.sqrt(s2)
        z = t * m / s
        g = mills(z)
        w = g * (g + z)
        for k, xk in x.items():
            if solo is not None and k not in solo:
                continue
            mk, vk = self.get(k)
            if vk <= 0:
                continue
            self.medias[k] = mk + t * xk * vk / s * g
            self.varianzas[k] = vk * max(1 - xk * xk * vk / s2 * w, 1e-9)

    def muestra(self, keys: list[str], r: random.Random) -> dict[str, float]:
        """Un sorteo de los pesos (muestreo de Thompson): media + desviación × normal estándar."""
        out = {}
        for k in keys:
            mk, vk = self.get(k)
            out[k] = mk + math.sqrt(vk) * r.gauss(0.0, 1.0)
        return out


def rng(*parts) -> random.Random:
    """Generador con semilla derivada del texto de `parts` (sha256): la misma decisión, el mismo sorteo."""
    seed = int(hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16], 16)
    return random.Random(seed)
