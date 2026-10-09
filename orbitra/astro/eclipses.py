"""Éclipses de Soleil et de Lune à venir (calculées, pas recopiées d'une liste)."""
import math

import astronomy

from .timeutil import iso

KINDS = {
    "Penumbral": "pénombrale",
    "Partial": "partielle",
    "Annular": "annulaire",
    "Total": "totale",
}


def _kind(k) -> str:
    return KINDS.get(k.name, k.name.lower())


def lunar(start: astronomy.Time, count: int = 6) -> list[dict]:
    out, e = [], astronomy.SearchLunarEclipse(start)
    for _ in range(count):
        out.append({
            "type": "lune",
            "kind": _kind(e.kind),
            "peak": iso(e.peak),
            # demi-durées des phases, en minutes (0 si la phase n'a pas lieu)
            "duration_total_min": round(2 * e.sd_total),
            "duration_partial_min": round(2 * e.sd_partial),
            "duration_penumbral_min": round(2 * e.sd_penum),
            "obscuration": round(e.obscuration, 3),
        })
        e = astronomy.NextLunarEclipse(e.peak)
    return out


def solar_global(start: astronomy.Time, count: int = 6) -> list[dict]:
    out, e = [], astronomy.SearchGlobalSolarEclipse(start)
    for _ in range(count):
        item = {"type": "soleil", "kind": _kind(e.kind), "peak": iso(e.peak)}
        # point de la Terre où l'éclipse est maximale : n'existe que si le cône
        # d'ombre touche la Terre (totale/annulaire), sinon la lib renvoie NaN
        if e.latitude is not None and not math.isnan(e.latitude):
            item["latitude"] = round(e.latitude, 2)
            item["longitude"] = round(e.longitude, 2)
        out.append(item)
        e = astronomy.NextGlobalSolarEclipse(e.peak)
    return out


def solar_local(start: astronomy.Time, observer: astronomy.Observer, count: int = 3) -> list[dict]:
    """Éclipses de Soleil visibles depuis la position de l'observateur."""
    out, e = [], astronomy.SearchLocalSolarEclipse(start, observer)
    for _ in range(count):
        out.append({
            "type": "soleil_local",
            "kind": _kind(e.kind),
            "start": iso(e.partial_begin.time),
            "peak": iso(e.peak.time),
            "end": iso(e.partial_end.time),
            "sun_altitude": round(e.peak.altitude, 1),
            "obscuration": round(e.obscuration, 3),
        })
        e = astronomy.NextLocalSolarEclipse(e.peak.time, observer)
    return out


def summary(start: astronomy.Time, observer: astronomy.Observer) -> dict:
    return {
        "lunar": lunar(start),
        "solar": solar_global(start),
        "local": solar_local(start, observer),
    }
