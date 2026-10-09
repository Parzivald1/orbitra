"""Prévision des passages d'un satellite au-dessus d'un observateur.

Chaîne de calcul :
    TLE --SGP4--> position dans le repère TEME (inertiel, centré sur la Terre)
        --rotation de la Terre (temps sidéral)--> repère ECEF (fixé à la Terre)
        --différence avec la position de l'observateur--> azimut / élévation

Un passage est « visible à l'œil nu » si le satellite est éclairé par le Soleil
alors que l'observateur est dans la nuit : c'est pour ça qu'on voit l'ISS
briller juste après le coucher du soleil.
"""
import math
from datetime import datetime, timedelta

import astronomy
from sgp4.api import Satrec, jday

from .timeutil import to_astro, iso

WGS84_A = 6378.137            # rayon équatorial (km)
WGS84_F = 1 / 298.257223563   # aplatissement de la Terre
EARTH_RADIUS = 6378.137


def gmst(jd_ut1: float) -> float:
    """Temps sidéral moyen de Greenwich (radians), formule IAU 1982."""
    t = (jd_ut1 - 2451545.0) / 36525.0
    seconds = 67310.54841 + (876600 * 3600 + 8640184.812866) * t + 0.093104 * t * t - 6.2e-6 * t**3
    return math.radians((seconds % 86400) / 240.0)


def geodetic_to_ecef(lat_deg: float, lon_deg: float, alt_km: float) -> tuple[float, float, float]:
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    e2 = WGS84_F * (2 - WGS84_F)
    N = WGS84_A / math.sqrt(1 - e2 * math.sin(lat) ** 2)
    return (
        (N + alt_km) * math.cos(lat) * math.cos(lon),
        (N + alt_km) * math.cos(lat) * math.sin(lon),
        (N * (1 - e2) + alt_km) * math.sin(lat),
    )


def teme_to_ecef(r: tuple, jd: float) -> tuple[float, float, float]:
    th = gmst(jd)
    c, s = math.cos(th), math.sin(th)
    return c * r[0] + s * r[1], -s * r[0] + c * r[1], r[2]


def look_angles(sat_ecef, obs_ecef, lat_deg, lon_deg) -> tuple[float, float, float]:
    """Azimut (°, 0 = nord), élévation (°) et distance (km) vus par l'observateur."""
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    dx, dy, dz = (sat_ecef[k] - obs_ecef[k] for k in range(3))
    east = -math.sin(lon) * dx + math.cos(lon) * dy
    north = -math.sin(lat) * math.cos(lon) * dx - math.sin(lat) * math.sin(lon) * dy + math.cos(lat) * dz
    up = math.cos(lat) * math.cos(lon) * dx + math.cos(lat) * math.sin(lon) * dy + math.sin(lat) * dz
    az = math.degrees(math.atan2(east, north)) % 360
    el = math.degrees(math.atan2(up, math.hypot(east, north)))
    return az, el, math.sqrt(dx * dx + dy * dy + dz * dz)


def _jd(dt: datetime) -> tuple[float, float]:
    return jday(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second + dt.microsecond / 1e6)


def compass(az: float) -> str:
    points = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"]
    return points[round(az / 22.5) % 16]


def sun_altitude(dt: datetime, lat: float, lon: float, alt_m: float) -> float:
    t = to_astro(dt)
    obs = astronomy.Observer(lat, lon, alt_m)
    eq = astronomy.Equator(astronomy.Body.Sun, t, obs, True, True)
    return astronomy.Horizon(t, obs, eq.ra, eq.dec, astronomy.Refraction.Normal).altitude


def is_sunlit(r_teme: tuple, dt: datetime) -> bool:
    """Modèle d'ombre cylindrique : le satellite est-il dans l'ombre de la Terre ?"""
    sun = astronomy.GeoVector(astronomy.Body.Sun, to_astro(dt), True)
    norm = math.sqrt(sun.x**2 + sun.y**2 + sun.z**2)
    s = (sun.x / norm, sun.y / norm, sun.z / norm)
    proj = sum(r_teme[k] * s[k] for k in range(3))
    if proj > 0:
        return True  # côté jour de la Terre
    perp = math.sqrt(max(0.0, sum(c * c for c in r_teme) - proj * proj))
    return perp > EARTH_RADIUS


class Observer:
    def __init__(self, sat: Satrec, lat: float, lon: float, alt_m: float):
        self.sat, self.lat, self.lon, self.alt_m = sat, lat, lon, alt_m
        self.ecef = geodetic_to_ecef(lat, lon, alt_m / 1000)

    def teme(self, dt: datetime):
        jd, fr = _jd(dt)
        err, r, _ = self.sat.sgp4(jd, fr)
        return None if err else r

    def look(self, dt: datetime):
        r = self.teme(dt)
        if r is None:
            return None
        jd, fr = _jd(dt)
        return look_angles(teme_to_ecef(r, jd + fr), self.ecef, self.lat, self.lon)

    def elevation(self, dt: datetime) -> float:
        look = self.look(dt)
        return look[1] if look else -90.0


def _crossing(obs: Observer, t0: datetime, t1: datetime) -> datetime:
    """Instant où l'élévation passe par 0°, par dichotomie (précision 1 s)."""
    up0 = obs.elevation(t0) >= 0
    while (t1 - t0).total_seconds() > 1:
        mid = t0 + (t1 - t0) / 2
        if (obs.elevation(mid) >= 0) == up0:
            t0 = mid
        else:
            t1 = mid
    return t1


def find_passes(l1: str, l2: str, lat: float, lon: float, alt_m: float,
                start: datetime, hours: float = 72, min_elevation: float = 10,
                step_s: int = 30) -> list[dict]:
    obs = Observer(Satrec.twoline2rv(l1, l2), lat, lon, alt_m)
    end = start + timedelta(hours=hours)
    step = timedelta(seconds=step_s)

    passes = []
    t, prev_up, rise = start, obs.elevation(start) >= 0, None
    while t < end:
        t_next = t + step
        up = obs.elevation(t_next) >= 0
        if up and not prev_up:
            rise = _crossing(obs, t, t_next)
        elif prev_up and not up and rise is not None:
            setting = _crossing(obs, t, t_next)
            p = _describe_pass(obs, rise, setting)
            if p["max_elevation"] >= min_elevation:
                passes.append(p)
            rise = None
        t, prev_up = t_next, up
    return passes


def _describe_pass(obs: Observer, rise: datetime, setting: datetime) -> dict:
    best_t, best = rise, obs.look(rise)
    t = rise
    while t <= setting:
        look = obs.look(t)
        if look and look[1] > best[1]:
            best_t, best = t, look
        t += timedelta(seconds=5)
    az_rise = obs.look(rise)[0]
    az_set = obs.look(setting)[0]
    dark = sun_altitude(best_t, obs.lat, obs.lon, obs.alt_m) < -6
    lit = is_sunlit(obs.teme(best_t), best_t)
    return {
        "rise": iso(rise),
        "max": iso(best_t),
        "set": iso(setting),
        "duration_s": round((setting - rise).total_seconds()),
        "max_elevation": round(best[1], 1),
        "range_km": round(best[2]),
        "rise_dir": compass(az_rise),
        "max_dir": compass(best[0]),
        "set_dir": compass(az_set),
        "visible": dark and lit,
    }
