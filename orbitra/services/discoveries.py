"""Découvertes et actualité spatiale.

- NASA Exoplanet Archive : les dernières exoplanètes confirmées
- Spaceflight News API : actualités des missions et découvertes
"""
from datetime import datetime, timezone

from .. import net
from ..cache import ttl_cache

EXO_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
NEWS_URL = "https://api.spaceflightnewsapi.net/v4/articles/"

EXO_COLUMNS = ("pl_name,hostname,disc_year,disc_pubdate,discoverymethod,disc_facility,"
               "pl_rade,pl_bmasse,pl_orbper,pl_eqt,sy_dist")

METHODS_FR = {
    "Transit": "Transit (baisse de luminosité de l'étoile)",
    "Radial Velocity": "Vitesse radiale (l'étoile « tangue »)",
    "Imaging": "Imagerie directe",
    "Microlensing": "Microlentille gravitationnelle",
    "Transit Timing Variations": "Variations du temps de transit",
    "Astrometry": "Astrométrie",
}


@ttl_cache(12 * 3600)
async def exoplanets(limit: int = 30) -> dict:
    # Piège : l'archive applique "top N" AVANT le "order by", donc le tri côté serveur
    # renvoie n'importe quoi. On filtre sur les deux dernières années et on trie ici.
    since = datetime.now(timezone.utc).year - 1
    rows = await net.get_json(EXO_URL, {
        "query": f"select {EXO_COLUMNS} from pscomppars where disc_year >= {since}",
        "format": "json",
    })
    rows.sort(key=lambda p: (p.get("disc_pubdate") or "", p.get("pl_name") or ""), reverse=True)
    latest = rows[:limit]
    count = await net.get_json(EXO_URL, {"query": "select count(*) as n from pscomppars", "format": "json"})
    for p in latest:
        p["method_fr"] = METHODS_FR.get(p.get("discoverymethod"), p.get("discoverymethod"))
    return {"total": count[0]["n"] if count else None, "latest": latest}


@ttl_cache(30 * 60)
async def news(limit: int = 24) -> list[dict]:
    data = await net.get_json(NEWS_URL, {"limit": limit, "ordering": "-published_at"})
    return [
        {k: a.get(k) for k in ("id", "title", "url", "image_url", "news_site", "summary", "published_at")}
        for a in data.get("results", [])
    ]
