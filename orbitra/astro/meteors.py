"""Pluies d'étoiles filantes : prochain pic et qualité d'observation.

Les dates viennent du calendrier de l'IMO (International Meteor Organization),
à ±1 jour près d'une année sur l'autre. Le vrai facteur qui change tout,
c'est la Lune : une pleine Lune au moment du pic efface la plupart des météores.
"""
import json
from datetime import date, datetime, timezone
from functools import lru_cache

import astronomy

from ..config import DATA_DIR
from .timeutil import to_astro


@lru_cache
def showers() -> list[dict]:
    return json.loads((DATA_DIR / "meteor_showers.json").read_text(encoding="utf-8"))


def _md(s: str) -> tuple[int, int]:
    m, d = s.split("-")
    return int(m), int(d)


def is_active(shower: dict, day: date) -> bool:
    start, end, today = _md(shower["start"]), _md(shower["end"]), (day.month, day.day)
    if start <= end:
        return start <= today <= end
    return today >= start or today <= end  # pluie à cheval sur deux années


def next_peak(shower: dict, day: date) -> date:
    m, d = _md(shower["peak"])
    peak = date(day.year, m, d)
    if (day - peak).days > 1:  # on garde le pic de la veille comme « en cours »
        peak = date(day.year + 1, m, d)
    return peak


def moon_illumination(day: date) -> float:
    # milieu de la nuit, heure de minuit UTC du jour suivant le soir du pic
    t = to_astro(datetime(day.year, day.month, day.day, 23, 0, tzinfo=timezone.utc))
    return astronomy.Illumination(astronomy.Body.Moon, t).phase_fraction


def rating(zhr: int, moon: float) -> str:
    """Note simple : taux horaire corrigé par la gêne lunaire."""
    score = zhr * (1 - 0.8 * moon)
    if score >= 60:
        return "excellente"
    if score >= 25:
        return "bonne"
    if score >= 10:
        return "moyenne"
    return "faible"


def upcoming(today: date | None = None) -> list[dict]:
    today = today or datetime.now(timezone.utc).date()
    out = []
    for s in showers():
        peak = next_peak(s, today)
        moon = moon_illumination(peak)
        out.append({
            **s,
            "peak_date": peak.isoformat(),
            "days_to_peak": (peak - today).days,
            "active": is_active(s, today),
            "moon_illumination": round(moon, 2),
            "rating": rating(s["zhr"], moon),
        })
    return sorted(out, key=lambda x: x["days_to_peak"])
