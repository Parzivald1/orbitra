"""« Ciel ce soir » : Soleil, Lune et planètes vus depuis la position de l'utilisateur."""
from datetime import datetime, timedelta

import astronomy
from astronomy import Body, Direction

from .timeutil import iso, to_astro, from_astro

PLANETS = [
    (Body.Mercury, "Mercure"), (Body.Venus, "Vénus"), (Body.Mars, "Mars"),
    (Body.Jupiter, "Jupiter"), (Body.Saturn, "Saturne"),
    (Body.Uranus, "Uranus"), (Body.Neptune, "Neptune"),
]

DARK_SUN_ALT = 6  # degrés sous l'horizon

PHASES = [
    (22.5, "Nouvelle lune"), (67.5, "Premier croissant"),
    (112.5, "Premier quartier"), (157.5, "Gibbeuse croissante"),
    (202.5, "Pleine lune"), (247.5, "Gibbeuse décroissante"),
    (292.5, "Dernier quartier"), (337.5, "Dernier croissant"),
    (360.1, "Nouvelle lune"),
]

# Les 88 constellations officielles (UAI), abréviation -> nom français
CONSTELLATIONS_FR = {
    "And": "Andromède", "Ant": "Machine pneumatique", "Aps": "Oiseau de paradis", "Aqr": "Verseau",
    "Aql": "Aigle", "Ara": "Autel", "Ari": "Bélier", "Aur": "Cocher", "Boo": "Bouvier", "Cae": "Burin",
    "Cam": "Girafe", "Cnc": "Cancer", "CVn": "Chiens de chasse", "CMa": "Grand Chien", "CMi": "Petit Chien",
    "Cap": "Capricorne", "Car": "Carène", "Cas": "Cassiopée", "Cen": "Centaure", "Cep": "Céphée",
    "Cet": "Baleine", "Cha": "Caméléon", "Cir": "Compas", "Col": "Colombe", "Com": "Chevelure de Bérénice",
    "CrA": "Couronne australe", "CrB": "Couronne boréale", "Crv": "Corbeau", "Crt": "Coupe", "Cru": "Croix du Sud",
    "Cyg": "Cygne", "Del": "Dauphin", "Dor": "Dorade", "Dra": "Dragon", "Equ": "Petit Cheval", "Eri": "Éridan",
    "For": "Fourneau", "Gem": "Gémeaux", "Gru": "Grue", "Her": "Hercule", "Hor": "Horloge", "Hya": "Hydre",
    "Hyi": "Hydre mâle", "Ind": "Indien", "Lac": "Lézard", "Leo": "Lion", "LMi": "Petit Lion", "Lep": "Lièvre",
    "Lib": "Balance", "Lup": "Loup", "Lyn": "Lynx", "Lyr": "Lyre", "Men": "Table", "Mic": "Microscope",
    "Mon": "Licorne", "Mus": "Mouche", "Nor": "Règle", "Oct": "Octant", "Oph": "Ophiuchus", "Ori": "Orion",
    "Pav": "Paon", "Peg": "Pégase", "Per": "Persée", "Phe": "Phénix", "Pic": "Peintre", "Psc": "Poissons",
    "PsA": "Poisson austral", "Pup": "Poupe", "Pyx": "Boussole", "Ret": "Réticule", "Sge": "Flèche",
    "Sgr": "Sagittaire", "Sco": "Scorpion", "Scl": "Sculpteur", "Sct": "Écu de Sobieski", "Ser": "Serpent",
    "Sex": "Sextant", "Tau": "Taureau", "Tel": "Télescope", "Tri": "Triangle", "TrA": "Triangle austral",
    "Tuc": "Toucan", "UMa": "Grande Ourse", "UMi": "Petite Ourse", "Vel": "Voiles", "Vir": "Vierge",
    "Vol": "Poisson volant", "Vul": "Petit Renard",
}


def constellation_fr(ra: float, dec: float) -> str:
    c = astronomy.Constellation(ra, dec)
    return CONSTELLATIONS_FR.get(c.symbol, c.name)
QUARTERS = ["Nouvelle lune", "Premier quartier", "Pleine lune", "Dernier quartier"]


def _event(body, obs, direction, t, days=1.5):
    ev = astronomy.SearchRiseSet(body, obs, direction, t, days)
    return iso(ev) if ev else None


def horizontal(body, t, obs):
    eq = astronomy.Equator(body, t, obs, True, True)
    hor = astronomy.Horizon(t, obs, eq.ra, eq.dec, astronomy.Refraction.Normal)
    return hor.altitude, hor.azimuth


def moon_phase(t) -> dict:
    angle = astronomy.MoonPhase(t)
    name = next(n for limit, n in PHASES if angle < limit)
    quarters, q = [], astronomy.SearchMoonQuarter(t)
    for _ in range(4):
        quarters.append({"name": QUARTERS[q.quarter], "date": iso(q.time)})
        q = astronomy.NextMoonQuarter(q)
    return {
        "angle": round(angle, 1),
        "name": name,
        "illumination": round(astronomy.Illumination(Body.Moon, t).phase_fraction, 3),
        "next_quarters": quarters,
    }


def tonight(lat: float, lon: float, alt_m: float, now: datetime) -> dict:
    obs = astronomy.Observer(lat, lon, alt_m)
    t = to_astro(now)

    sun_alt = horizontal(Body.Sun, t, obs)[0]
    sunset = astronomy.SearchRiseSet(Body.Sun, obs, Direction.Set, t, 1.5)
    sunrise = astronomy.SearchRiseSet(Body.Sun, obs, Direction.Rise, t, 1.5)
    dusk = astronomy.SearchAltitude(Body.Sun, obs, Direction.Set, t, 1.5, -12)

    # Fenêtre d'observation = Soleil à plus de 6° sous l'horizon (fin du crépuscule civil).
    # Correctif : avant, on prenait coucher -> lever, et Mercure était « visible »
    # en plein crépuscule, Jupiter « au mieux » après le lever du Soleil.
    night_start = t if sun_alt < -DARK_SUN_ALT else astronomy.SearchAltitude(Body.Sun, obs, Direction.Set, t, 1.5, -DARK_SUN_ALT)
    night_end = astronomy.SearchAltitude(Body.Sun, obs, Direction.Rise, night_start, 1.5, -DARK_SUN_ALT) if night_start else None
    start = from_astro(night_start) if night_start else now
    end = from_astro(night_end) if night_end else start + timedelta(hours=8)
    samples = [start + (end - start) * k / 24 for k in range(25)]

    planets = []
    for body, name in PLANETS:
        best_alt, best_time = -90.0, None
        for s in samples:
            alt, _ = horizontal(body, to_astro(s), obs)
            if alt > best_alt:
                best_alt, best_time = alt, s
        alt_now, az_now = horizontal(body, t, obs)
        eqj = astronomy.Equator(body, t, obs, False, True)
        planets.append({
            "name": name,
            "altitude_now": round(alt_now, 1),
            "azimuth_now": round(az_now, 1),
            "rise": _event(body, obs, Direction.Rise, t),
            "set": _event(body, obs, Direction.Set, t),
            "magnitude": round(astronomy.Illumination(body, t).mag, 1),
            "constellation": constellation_fr(eqj.ra, eqj.dec),
            "best_time": iso(best_time) if best_time else None,
            "best_altitude": round(best_alt, 1),
            # visible : au moins 10° au-dessus de l'horizon pendant la nuit noire
            "visible_tonight": best_alt >= 10,
        })

    return {
        "sun": {
            "set": iso(sunset) if sunset else None,
            "rise": iso(sunrise) if sunrise else None,
            "dark": iso(dusk) if dusk else None,
            "night_start": iso(start),
            "night_end": iso(end),
            "altitude_now": round(horizontal(Body.Sun, t, obs)[0], 1),
        },
        "moon": {
            **moon_phase(t),
            "rise": _event(Body.Moon, obs, Direction.Rise, t),
            "set": _event(Body.Moon, obs, Direction.Set, t),
            "altitude_now": round(horizontal(Body.Moon, t, obs)[0], 1),
        },
        "planets": planets,
    }
