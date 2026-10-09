"""Galerie : clichés remarquables de la Lune et des planètes, enregistrés automatiquement.

Une machine ne sait pas dire qu'une photo est « belle », mais elle peut MESURER si on voit
bien l'astre. Un cliché n'est enregistré que s'il passe deux filtres :

1. Le texte (titre, description, mots-clés de la NASA) :
   - la Lune ou une planète est nommée dans le titre
   - ce n'est pas une vue d'artiste, une simulation, une carte, un son, un graphique
   - ce n'est pas un événement au sol (lever de Lune sur une ville, lancement, cérémonie…)
2. L'image elle-même (module imagecheck) : l'astre est seul, entier, net,
   sur le fond noir de l'espace.

Historique : la v1 ne filtrait que le texte et gardait un arbre planté avec des graines
d'Apollo 14, des cartes, des gros plans de sol martien et des doublons. L'analyse d'image
règle le problème à la source.
"""
import asyncio
import json
import re

from .. import net
from ..cache import ttl_cache
from ..config import CACHE_DIR
from . import imagecheck

NASA_IMAGES = "https://images-api.nasa.gov/search"
GALLERY_FILE = CACHE_DIR / "gallery.json"
PER_TARGET = 12

# cible -> (nom affiché, motif reconnu dans le titre, recherches ciblées vers les vues globales)
TARGETS = {
    "lune": ("Lune", r"\b(moon|lunar|lune)\b",
             ["full Moon", "Moon Lunar Reconnaissance Orbiter", "Moon Artemis Orion", "lunar far side", "Moon Galileo spacecraft"]),
    "mercure": ("Mercure", r"\b(mercury|mercure)\b", ["Mercury MESSENGER global", "Mercury Mariner 10"]),
    "venus": ("Vénus", r"\b(venus|vénus)\b", ["Venus Mariner 10", "Venus Galileo", "Venus Akatsuki", "Venus global view"]),
    "mars": ("Mars", r"\bmars\b", ["Mars Hubble", "Mars global view", "Mars Viking orbiter global", "Mars Rosetta"]),
    "jupiter": ("Jupiter", r"\bjupiter\b", ["Jupiter Hubble", "Jupiter Juno full disk", "Jupiter Webb", "Jupiter Cassini"]),
    "saturne": ("Saturne", r"\b(saturn|saturne)\b", ["Saturn Cassini", "Saturn Hubble", "Saturn Webb"]),
    "uranus": ("Uranus", r"\buranus\b", ["Uranus Voyager 2", "Uranus Webb", "Uranus Hubble"]),
    "neptune": ("Neptune", r"\bneptune\b", ["Neptune Voyager 2", "Neptune Webb", "Neptune Hubble"]),
}

NOT_A_PHOTO = re.compile(
    r"artist|illustration|concept|render|simulat|animation|diagram|graphic|infographic|chart|\bmaps?\b|"
    r"model of|poster|logo|sound|audio|data visuali|plot|spectrum|timeline|comparison|vue d'artiste", re.I)
OFF_TOPIC = re.compile(
    r"\b(rises?|rising|sets?|setting|over the|above the|behind|silhouette|skyline|city|pad|rocket|launch|"
    r"sls|team|mission control|press|briefing|ceremony|engineer|technician|spacesuit|training|clean room|"
    r"meeting|award|drone|hill|tree|helicopter|selfie|rover|lander|sample|"
    r"montage|collage|sequence|series|rotation|images|views|pictures|anniversary)\b", re.I)  # plusieurs images = montage
# Titres consacrés à une lune d'une planète (ex. « Triton - Neptune Largest Satellite ») : ce n'est pas la planète
MOON_OF_PLANET = re.compile(
    r"\b(triton|titan|enceladus|mimas|iapetus|rhea|dione|tethys|miranda|ariel|umbriel|titania|oberon|"
    r"phobos|deimos|ganymede|callisto|europa|charon|largest satellite)\b", re.I)


def target_of(title: str) -> str | None:
    for key, (_, pattern, _) in TARGETS.items():
        if re.search(pattern, title, re.I):
            return key
    return None


def passes_text(title: str, description: str = "", keywords: list[str] | None = None) -> str | None:
    """Renvoie la cible si le texte est compatible avec une vraie photo de l'astre."""
    text = " ".join([title, description[:600], " ".join(keywords or [])])
    if NOT_A_PHOTO.search(text) or OFF_TOPIC.search(title) or MOON_OF_PLANET.search(title):
        return None
    return target_of(title)


# ---------- Fichier de la galerie (persistant) ----------

def load() -> dict:
    try:
        data = json.loads(GALLERY_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"items": [], "checked": {}}
    if isinstance(data, list):  # ancien format (v1) : on repart de zéro avec les nouvelles règles
        return {"items": [], "checked": {}}
    return data


def save(data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    GALLERY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------- Collecte ----------

async def _candidates(key: str) -> list[dict]:
    found, seen = [], set()
    for query in TARGETS[key][2]:
        try:
            data = await net.get_json(NASA_IMAGES, {"q": query, "media_type": "image", "page_size": 30})
        except Exception:
            continue
        for item in data.get("collection", {}).get("items", []):
            meta = (item.get("data") or [{}])[0]
            title = (meta.get("title") or "").strip()
            nasa_id = meta.get("nasa_id")
            thumb = (item.get("links") or [{}])[0].get("href", "")
            if not nasa_id or nasa_id in seen or "~" not in thumb:
                continue
            if passes_text(title, meta.get("description") or "", meta.get("keywords")) != key:
                continue
            seen.add(nasa_id)
            base = thumb.rsplit("~", 1)[0]
            found.append({
                "id": f"nasa:{nasa_id}",
                "target": key,
                "title": title,
                "date": (meta.get("date_created") or "")[:10],
                "check_url": f"{base}~thumb.jpg",
                # correctif : la taille « medium » n'existe pas pour les anciennes images,
                # on prend l'aperçu réellement fourni par l'API
                "thumb": thumb,
                "full": f"{base}~orig.jpg",
                "credit": f"NASA {meta.get('center') or ''}".strip(),
                "source": "NASA Image and Video Library",
                "description": (meta.get("description") or "")[:600],
            })
    return found


_slots = asyncio.Semaphore(6)


async def _verdict(c: dict) -> dict | None:
    async with _slots:
        try:
            r = await net.client().get(c["check_url"])
            r.raise_for_status()
            return imagecheck.analyse(r.content)
        except Exception:
            return None  # image illisible : on réessaiera au prochain passage


@ttl_cache(6 * 3600)
async def refresh() -> dict:
    """Cherche de nouveaux clichés, les analyse, et enregistre ceux qui passent (toutes les 6 h)."""
    data = load()
    items, checked = data["items"], data["checked"]  # checked : id -> True/False (déjà analysé)
    titles = {i["title"].lower() for i in items}

    for key in TARGETS:
        have = sum(1 for i in items if i["target"] == key)
        if have >= PER_TARGET:
            continue
        candidates = [c for c in await _candidates(key) if c["id"] not in checked and c["title"].lower() not in titles]
        verdicts = await asyncio.gather(*(_verdict(c) for c in candidates))
        for c, v in zip(candidates, verdicts):
            if v is None:
                continue
            checked[c["id"]] = v["ok"]
            if v["ok"] and have < PER_TARGET and c["title"].lower() not in titles:
                c.pop("check_url")
                c["analysis"] = v["metrics"]
                items.append(c)
                titles.add(c["title"].lower())
                have += 1

    items.sort(key=lambda i: (i["target"], i.get("date") or ""), reverse=False)
    save({"items": items, "checked": checked})
    return {"items": items, "checked": len(checked)}


async def gallery() -> dict:
    data = await refresh()
    items = data["items"]
    return {
        "criteria": [
            "Vraie photo publiée par la NASA (pas de vue d'artiste, de carte ni de simulation)",
            "La Lune ou une planète est le sujet nommé dans le titre",
            "Analyse de l'image : l'astre est seul, entier et net sur le fond noir de l'espace",
        ],
        "checked": data["checked"],
        "targets": {k: v[0] for k, v in TARGETS.items()},
        "counts": {k: sum(1 for i in items if i["target"] == k) for k in TARGETS},
        "items": items,
    }
