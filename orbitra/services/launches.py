"""Prochains lancements de fusées (The Space Devs - Launch Library 2).

L'API gratuite est limitée à 15 requêtes par heure : cache d'une heure obligatoire.
"""
from .. import net
from ..cache import ttl_cache

LL2_URL = "https://ll.thespacedevs.com/2.2.0/launch/upcoming/"


def _get(d, *path):
    for p in path:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    return d


def simplify(l: dict) -> dict:
    return {
        "id": l.get("id"),
        "name": l.get("name"),
        "net": l.get("net"),  # « No Earlier Than » : date prévue, pas avant
        "window_start": l.get("window_start"),
        "status": _get(l, "status", "name"),
        "status_abbrev": _get(l, "status", "abbrev"),
        "provider": _get(l, "launch_service_provider", "name"),
        "rocket": _get(l, "rocket", "configuration", "full_name"),
        "mission": _get(l, "mission", "name"),
        "mission_type": _get(l, "mission", "type"),
        "description": _get(l, "mission", "description"),
        "orbit": _get(l, "mission", "orbit", "name"),
        "pad": _get(l, "pad", "name"),
        "location": _get(l, "pad", "location", "name"),
        "image": l.get("image"),
        "probability": l.get("probability"),
    }


@ttl_cache(3600)
async def upcoming(limit: int = 20) -> list[dict]:
    data = await net.get_json(LL2_URL, {"limit": limit, "mode": "normal"})
    return [simplify(l) for l in data.get("results", [])]
