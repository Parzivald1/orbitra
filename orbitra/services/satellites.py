"""Catalogue de tout ce qui est en orbite, à partir des TLE publics de CelesTrak.

Un TLE (Two-Line Element set) décrit l'orbite d'un objet en deux lignes de texte.
Le navigateur s'en sert ensuite pour calculer la position de chaque satellite en
temps réel (algorithme SGP4).

Attention : CelesTrak ne met ses données à jour que toutes les 2 h et refuse
les téléchargements répétés (il renvoie un message au lieu des TLE). Chaque groupe
est donc sauvegardé sur disque et on ne le redemande pas plus d'une fois toutes les 2 h.
"""
import asyncio
import os
import time
from datetime import datetime, timezone

from .. import net
from ..cache import ttl_cache
from ..config import CACHE_DIR

CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php"
REFRESH_SECONDS = 2 * 3600
NOT_UPDATED_MARKER = "has not updated since"

# Groupes thématiques : servent seulement à classer les satellites du groupe "active".
# L'ordre compte : le premier groupe qui contient un satellite donne sa catégorie.
THEME_GROUPS = [
    ("stations", "station"),
    ("science", "science"),
    ("weather", "meteo"),
    ("resource", "observation"),
    ("gnss", "navigation"),
]

# Nuages de débris issus de collisions ou de tirs antisatellites
DEBRIS_GROUPS = [
    "fengyun-1c-debris",   # tir antisatellite chinois, 2007
    "cosmos-2251-debris",  # collision Iridium 33 / Cosmos 2251, 2009
    "iridium-33-debris",
    "cosmos-1408-debris",  # tir antisatellite russe, 2021
]

# Si "active" est indisponible et pas encore en cache : on reconstruit avec ces groupes
FALLBACK_GROUPS = ["starlink", "oneweb", "geo", "iridium-NEXT", "planet", "spire"]

NAME_RULES = [
    ("STARLINK", "starlink"),
    ("ONEWEB", "constellation"),
    ("IRIDIUM", "constellation"),
    ("KUIPER", "constellation"),
    ("GLOBALSTAR", "constellation"),
    ("ORBCOMM", "constellation"),
    ("QIANFAN", "constellation"),
    ("FLOCK", "observation"),
    ("LEMUR", "observation"),
]


def parse_tle(text: str) -> list[dict]:
    """Découpe un fichier TLE au format 3 lignes (nom, ligne 1, ligne 2)."""
    lines = [l.rstrip() for l in text.splitlines() if l.strip()]
    sats = []
    i = 0
    while i + 2 < len(lines):
        name, l1, l2 = lines[i], lines[i + 1], lines[i + 2]
        if l1.startswith("1 ") and l2.startswith("2 "):
            sats.append({
                "id": l2[2:7].strip(),
                "name": name.strip().removeprefix("0 "),
                "l1": l1,
                "l2": l2,
            })
            i += 3
        else:
            i += 1  # ligne inattendue : on se recale
    return sats


def classify(name: str, theme: str | None) -> str:
    if theme == "station":
        return "station"
    upper = name.upper()
    for prefix, cat in NAME_RULES:
        if upper.startswith(prefix):
            return cat
    return theme or "autre"


def _cache_file(group: str):
    return CACHE_DIR / f"{group}.tle"


async def fetch_group(group: str) -> str | None:
    """Renvoie le texte TLE d'un groupe, depuis le disque si possible."""
    path = _cache_file(group)
    if path.exists() and time.time() - path.stat().st_mtime < REFRESH_SECONDS:
        return path.read_text()
    try:
        text = await net.get_text(CELESTRAK_URL, {"GROUP": group, "FORMAT": "tle"})
    except Exception:
        text = None
    if text and NOT_UPDATED_MARKER not in text and parse_tle(text):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return text
    if path.exists():
        # CelesTrak dit "rien de neuf" (ou est en panne) : on garde notre copie
        # et on repousse la prochaine demande de 2 h.
        os.utime(path)
        return path.read_text()
    return None


@ttl_cache(REFRESH_SECONDS)
async def catalog() -> dict:
    groups = ["active"] + [g for g, _ in THEME_GROUPS] + DEBRIS_GROUPS
    texts = dict(zip(groups, await asyncio.gather(*(fetch_group(g) for g in groups))))

    themes: dict[str, str] = {}
    for group, cat in THEME_GROUPS:
        for s in parse_tle(texts[group] or ""):
            themes.setdefault(s["id"], cat)

    sats: dict[str, dict] = {}
    if texts["active"]:
        for s in parse_tle(texts["active"]):
            sats[s["id"]] = s
    else:
        extra = await asyncio.gather(*(fetch_group(g) for g in FALLBACK_GROUPS))
        for text in [texts[g] for g, _ in THEME_GROUPS] + list(extra):
            for s in parse_tle(text or ""):
                sats.setdefault(s["id"], s)

    for s in sats.values():
        s["cat"] = classify(s["name"], themes.get(s["id"]))

    for group in DEBRIS_GROUPS:
        for s in parse_tle(texts[group] or ""):
            if s["id"] not in sats:
                s["cat"] = "debris"
                sats[s["id"]] = s

    if not sats:
        raise RuntimeError("Aucune donnée CelesTrak disponible")

    counts: dict[str, int] = {}
    for s in sats.values():
        counts[s["cat"]] = counts.get(s["cat"], 0) + 1

    return {
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "CelesTrak (celestrak.org)",
        "complete": bool(texts["active"]),
        "count": len(sats),
        "categories": counts,
        "satellites": list(sats.values()),
    }


async def get_tle(norad_id: str) -> dict | None:
    data = await catalog()
    for s in data["satellites"]:
        if s["id"] == norad_id:
            return s
    return None
