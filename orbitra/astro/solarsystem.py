"""Vue 3D du système solaire : orbites et positions des planètes et petits corps.

Repère commun : héliocentrique écliptique J2000, en UA.
- Planètes : modèle VSOP87 via astronomy-engine (très précis)
- Comètes et astéroïdes : notre propre calcul képlérien (module kepler)
"""
import math
from functools import lru_cache

import astronomy
from astronomy import Body

from . import kepler
from .timeutil import J2000_JD, from_jd, iso

PLANETS = [
    # corps, nom, période (jours), couleur, rayon (km)
    (Body.Mercury, "Mercure", 87.969, "#b5aa9f", 2440),
    (Body.Venus, "Vénus", 224.701, "#e8c37a", 6052),
    (Body.Earth, "Terre", 365.256, "#4f9dff", 6371),
    (Body.Mars, "Mars", 686.98, "#e2683c", 3390),
    (Body.Jupiter, "Jupiter", 4332.59, "#d9b38c", 69911),
    (Body.Saturn, "Saturne", 10759.22, "#e8d49b", 58232),
    (Body.Uranus, "Uranus", 30688.5, "#9fe3ec", 25362),
    (Body.Neptune, "Neptune", 60182.0, "#5b7cff", 24622),
]

_EQJ_TO_ECL = astronomy.Rotation_EQJ_ECL()


def _ecliptic(body: Body, t: astronomy.Time) -> tuple[float, float, float]:
    v = astronomy.RotateVector(_EQJ_TO_ECL, astronomy.HelioVector(body, t))
    return v.x, v.y, v.z


def _t(jd: float) -> astronomy.Time:
    return astronomy.Time(jd - J2000_JD)


def _round(p):
    return [round(c, 4) for c in p]


@lru_cache
def planet_orbits(samples: int = 240) -> list[dict]:
    out = []
    for body, name, period, color, radius in PLANETS:
        pts = [_ecliptic(body, _t(J2000_JD + period * k / samples)) for k in range(samples + 1)]
        out.append({"name": name, "color": color, "radius_km": radius,
                    "period_days": period, "orbit": [_round(p) for p in pts]})
    return out


def small_body_orbits(bodies: list[dict]) -> list[dict]:
    out = []
    for b in bodies:
        el = b["elements"]
        out.append({
            "name": b["name"],
            "sstr": b["sstr"],
            "type": b["type"],
            "note": b["note"],
            "elements": el,
            "period_years": round(kepler.period_days(el) / 365.25, 2) if kepler.period_days(el) else None,
            "orbit": [_round(p) for p in kepler.orbit_path(el)],
        })
    return out


def _dist(a, b):
    return math.dist(a, b)


def positions(jd: float, bodies: list[dict]) -> dict:
    t = _t(jd)
    earth = _ecliptic(Body.Earth, t)
    planets = []
    for body, name, *_ in PLANETS:
        p = _ecliptic(body, t)
        planets.append({"name": name, "pos": _round(p),
                        "sun_au": round(math.hypot(*p), 3),
                        "earth_au": round(_dist(p, earth), 3)})
    small = []
    for b in bodies:
        el = b["elements"]
        p = kepler.position(el, jd)
        nxt = kepler.next_perihelion(el, jd)
        period = kepler.period_days(el)
        last = (nxt - period) if (nxt and period) else (el["tp"] if el["tp"] <= jd else None)
        small.append({
            "name": b["name"],
            "pos": _round(p),
            "sun_au": round(math.hypot(*p), 3),
            "earth_au": round(_dist(p, earth), 3),
            "next_perihelion": iso(from_jd(nxt)) if nxt else None,
            "last_perihelion": iso(from_jd(last)) if last else None,
        })
    return {"date": iso(from_jd(jd)), "planets": planets, "small_bodies": small}
