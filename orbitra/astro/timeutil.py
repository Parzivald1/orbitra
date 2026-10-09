"""Conversions de dates entre Python, jours juliens et astronomy-engine."""
from datetime import datetime, timedelta, timezone

import astronomy

J2000_JD = 2451545.0  # 1er janvier 2000 à 12 h TT, l'origine des temps des astronomes
J2000 = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_jd(dt: datetime) -> float:
    """Date UTC -> jour julien."""
    return J2000_JD + (dt - J2000).total_seconds() / 86400.0


def from_jd(jd: float) -> datetime:
    return J2000 + timedelta(days=jd - J2000_JD)


def to_astro(dt: datetime) -> astronomy.Time:
    return astronomy.Time((dt - J2000).total_seconds() / 86400.0)


def from_astro(t: astronomy.Time) -> datetime:
    return J2000 + timedelta(days=t.ut)


def iso(dt: datetime | astronomy.Time) -> str:
    if isinstance(dt, astronomy.Time):
        dt = from_astro(dt)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
