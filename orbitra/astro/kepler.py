"""Mécanique orbitale à deux corps : position d'une comète ou d'un astéroïde
autour du Soleil à partir de ses éléments orbitaux.

On ne tient compte que de l'attraction du Soleil (pas des planètes ni du dégazage
des comètes) : c'est largement assez précis pour la visualisation, mais ça dérive
pour des dates très éloignées du dernier passage au périhélie.

Éléments utilisés (ceux du JPL) :
    e   excentricité           (0 = cercle, <1 = ellipse, 1 = parabole, >1 = hyperbole)
    q   distance au périhélie  (UA)
    i   inclinaison            (degrés, par rapport à l'écliptique)
    om  longitude du nœud ascendant Ω (degrés)
    w   argument du périhélie ω (degrés)
    tp  date du passage au périhélie (jour julien)

Le résultat est en coordonnées héliocentriques écliptiques J2000, en UA.
"""
import math

K_GAUSS = 0.01720209895  # constante de Gauss (rad/jour) : racine de G·M_soleil en UA³/j²
PARABOLIC_TOL = 1e-6


def solve_kepler_elliptic(M: float, e: float) -> float:
    """Résout l'équation de Kepler  M = E - e·sin(E)  par la méthode de Newton."""
    M = math.remainder(M, 2 * math.pi)  # ramène M dans [-π, π]
    E = M if e < 0.8 else math.copysign(math.pi, M)
    for _ in range(100):
        dE = (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
        E -= dE
        if abs(dE) < 1e-13:
            break
    return E


def solve_kepler_hyperbolic(M: float, e: float) -> float:
    """Résout la version hyperbolique  M = e·sinh(H) - H."""
    H = math.copysign(math.log(2 * abs(M) / e + 1.8), M)
    for _ in range(200):
        dH = (e * math.sinh(H) - H - M) / (e * math.cosh(H) - 1)
        H -= dH
        if abs(dH) < 1e-13:
            break
    return H


def perifocal(el: dict, jd: float) -> tuple[float, float]:
    """Position dans le plan de l'orbite (x vers le périhélie)."""
    e, q = el["e"], el["q"]
    dt = jd - el["tp"]
    if abs(e - 1) < PARABOLIC_TOL:
        # Parabole : équation de Barker  s + s³/3 = B  avec s = tan(ν/2)
        B = K_GAUSS * dt / math.sqrt(2 * q**3)
        W = 1.5 * B
        Y = math.cbrt(W + math.sqrt(W * W + 1))
        s = Y - 1 / Y
        nu = 2 * math.atan(s)
        r = q * (1 + s * s)
        return r * math.cos(nu), r * math.sin(nu)
    if e < 1:
        a = q / (1 - e)
        M = K_GAUSS / a**1.5 * dt
        E = solve_kepler_elliptic(M, e)
        return a * (math.cos(E) - e), a * math.sqrt(1 - e * e) * math.sin(E)
    a = q / (e - 1)
    M = K_GAUSS / a**1.5 * dt
    H = solve_kepler_hyperbolic(M, e)
    return a * (e - math.cosh(H)), a * math.sqrt(e * e - 1) * math.sinh(H)


def rotate_to_ecliptic(el: dict, xp: float, yp: float) -> tuple[float, float, float]:
    """Passe du plan de l'orbite au repère écliptique (3 rotations : ω, i, Ω)."""
    O, i, w = (math.radians(el[k]) for k in ("om", "i", "w"))
    cO, sO, ci, si, cw, sw = math.cos(O), math.sin(O), math.cos(i), math.sin(i), math.cos(w), math.sin(w)
    x = (cO * cw - sO * sw * ci) * xp + (-cO * sw - sO * cw * ci) * yp
    y = (sO * cw + cO * sw * ci) * xp + (-sO * sw + cO * cw * ci) * yp
    z = (sw * si) * xp + (cw * si) * yp
    return x, y, z


def position(el: dict, jd: float) -> tuple[float, float, float]:
    return rotate_to_ecliptic(el, *perifocal(el, jd))


def period_days(el: dict) -> float | None:
    if el["e"] >= 1:
        return None  # orbite ouverte : l'objet ne reviendra jamais
    a = el["q"] / (1 - el["e"])
    return 2 * math.pi / K_GAUSS * a**1.5


def next_perihelion(el: dict, jd_now: float) -> float | None:
    """Jour julien du prochain passage au périhélie (ou du seul, si orbite ouverte)."""
    P = period_days(el)
    if P is None:
        return el["tp"] if el["tp"] >= jd_now else None
    n = math.ceil((jd_now - el["tp"]) / P)
    return el["tp"] + n * P


def orbit_path(el: dict, r_max: float = 60.0, samples: int = 360) -> list[tuple[float, float, float]]:
    """Points de la trajectoire complète (coupée à r_max UA pour les orbites géantes)."""
    e, q = el["e"], el["q"]
    p = q * (1 + e)  # paramètre de la conique : r = p / (1 + e·cos ν)
    aphelion = q * (1 + e) / (1 - e) if e < 1 else math.inf
    if aphelion <= r_max:
        nu_max = math.pi
    else:
        nu_max = math.acos(max(-1.0, min(1.0, (p / r_max - 1) / e)))
    pts = []
    for k in range(samples + 1):
        nu = -nu_max + 2 * nu_max * k / samples
        r = p / (1 + e * math.cos(nu))
        pts.append(rotate_to_ecliptic(el, r * math.cos(nu), r * math.sin(nu)))
    return pts
