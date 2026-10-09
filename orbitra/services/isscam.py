"""Caméra embarquée de l'ISS : les vraies photos prises par les astronautes.

Deux sources de la NASA :
1. NASA Image and Video Library (sans clé) : sélection de photos de l'équipage, avec légende.
2. Gateway to Astronaut Photography of Earth (eol.jsc.nasa.gov, clé API gratuite) :
   TOUTES les photos, avec l'heure exacte et le point survolé (« nadir »). Les astronautes
   prennent souvent des séquences (une photo par seconde) : mises bout à bout, elles forment
   un vrai film du trajet de la station, sans aucune image de synthèse.
"""
import os
from datetime import datetime, timedelta, timezone

from .. import net
from ..cache import ttl_cache

NASA_IMAGES = "https://images-api.nasa.gov/search"
EOL_API = "https://eol.jsc.nasa.gov/SearchPhotos/PhotosDatabaseAPI/PhotosDatabaseAPI.pl"
EOL_IMAGES = "https://eol.jsc.nasa.gov/DatabaseImages/"

MIN_SEQUENCE = 20      # au moins 20 photos d'affilée pour faire un film
MAX_GAP_SECONDS = 3    # au-delà de 3 s entre deux photos, la séquence est coupée


def eol_key() -> str | None:
    return os.environ.get("EOL_API_KEY") or None


@ttl_cache(6 * 3600)
async def crew_photos(limit: int = 36) -> list[dict]:
    """Dernières photos de l'équipage publiées dans la photothèque de la NASA (sans clé)."""
    year = datetime.now(timezone.utc).year
    data = await net.get_json(NASA_IMAGES, {
        "q": "International Space Station Earth", "center": "JSC",
        "media_type": "image", "year_start": year - 1, "page_size": 100,
    })
    out = []
    for item in data.get("collection", {}).get("items", []):
        meta = (item.get("data") or [{}])[0]
        nasa_id = meta.get("nasa_id", "")
        # seuls les identifiants « iss0XXe… » sont des photos prises à bord par l'équipage
        if not nasa_id.lower().startswith("iss"):
            continue
        thumb = (item.get("links") or [{}])[0].get("href", "")
        base = thumb.rsplit("~", 1)[0] if "~" in thumb else None
        if not base:
            continue
        out.append({
            "id": nasa_id,
            "title": meta.get("title", "").strip(),
            "description": (meta.get("description") or "")[:600],
            "date": (meta.get("date_created") or "")[:10],
            "thumb": thumb,
            "full": f"{base}~orig.jpg",
        })
    out.sort(key=lambda p: (p["date"], p["id"]), reverse=True)
    return out[:limit]


def _frame_number(frame: str) -> int | None:
    digits = "".join(c for c in frame if c.isdigit())
    return int(digits) if digits else None


def _when(pdate: str, ptime: str) -> datetime | None:
    try:
        return datetime.strptime(f"{pdate}{ptime.zfill(6)}", "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def build_sequences(rows: list[dict]) -> list[dict]:
    """Regroupe les photos consécutives (même mission, numéros qui se suivent, < 3 s d'écart)."""
    photos = {}
    for r in rows:
        key = (r.get("nadir.mission"), r.get("nadir.frame"))
        p = photos.setdefault(key, {"mission": key[0], "frame": key[1], "files": {}})
        p["time"] = _when(str(r.get("nadir.pdate", "")), str(r.get("nadir.ptime", "")))
        p["lat"], p["lon"] = r.get("nadir.lat"), r.get("nadir.lon")
        p["sun"] = r.get("nadir.elev")
        directory = r.get("images.directory") or ""
        size = "small" if "/small/" in f"/{directory}/" else "large" if "/large/" in f"/{directory}/" else None
        if size:
            p["files"][size] = f"{EOL_IMAGES}{directory}/{r.get('images.filename')}"

    usable = [p for p in photos.values() if p["time"] and "small" in p["files"] and _frame_number(p["frame"] or "") is not None]
    usable.sort(key=lambda p: (p["mission"], _frame_number(p["frame"])))

    sequences, current = [], []
    for p in usable:
        prev = current[-1] if current else None
        if prev and prev["mission"] == p["mission"] \
                and _frame_number(p["frame"]) == _frame_number(prev["frame"]) + 1 \
                and 0 <= (p["time"] - prev["time"]).total_seconds() <= MAX_GAP_SECONDS:
            current.append(p)
        else:
            if len(current) >= MIN_SEQUENCE:
                sequences.append(current)
            current = [p]
    if len(current) >= MIN_SEQUENCE:
        sequences.append(current)

    out = []
    for seq in sequences:
        # on garde les séquences de jour (Soleil au-dessus de l'horizon au point survolé)
        sun = [s["sun"] for s in seq if isinstance(s["sun"], (int, float))]
        daylight = bool(sun) and sum(sun) / len(sun) > 0
        out.append({
            "id": f"{seq[0]['mission']}-E-{seq[0]['frame']}",
            "mission": seq[0]["mission"],
            "start": seq[0]["time"].isoformat(),
            "end": seq[-1]["time"].isoformat(),
            "count": len(seq),
            "daylight": daylight,
            "frames": [{
                "src": s["files"]["small"],
                "hd": s["files"].get("large"),
                "time": s["time"].isoformat(),
                "lat": s["lat"], "lon": s["lon"],
            } for s in seq],
        })
    return sorted(out, key=lambda s: (s["daylight"], s["count"]), reverse=True)


@ttl_cache(24 * 3600)
async def sequences(day: str) -> dict:
    """Séquences de photos prises à une date donnée (AAAAMMJJ). Nécessite la clé EOL."""
    key = eol_key()
    if not key:
        return {"enabled": False, "sequences": []}
    if not (len(day) == 8 and day.isdigit()):
        raise ValueError("date attendue au format AAAAMMJJ")
    fields = ["nadir|mission", "nadir|frame", "nadir|pdate", "nadir|ptime", "nadir|lat", "nadir|lon",
              "nadir|elev", "images|directory", "images|filename"]
    rows = await net.get_json(EOL_API, {
        "query": f"nadir|pdate|eq|{day}",
        "return": "|".join(fields),
        "key": key,
    })
    if isinstance(rows, dict) and rows.get("error"):
        raise RuntimeError(f"API photos de l'ISS : {rows['error']}")
    return {"enabled": True, "date": day, "sequences": build_sequences(rows if isinstance(rows, list) else [])}


def recent_days(n: int = 10) -> list[str]:
    """Les photos sont publiées avec quelques jours de retard : on propose les derniers jours."""
    today = datetime.now(timezone.utc).date()
    return [(today - timedelta(days=d)).strftime("%Y%m%d") for d in range(2, 2 + n)]
