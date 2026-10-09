"""Caméras spatiales réelles : les dernières images publiées par les sondes et satellites.

Rien n'est simulé : chaque image est le dernier fichier publié par l'agence, et on affiche
l'heure réelle de la prise de vue (en-tête Last-Modified ou métadonnées de l'API).
Si un flux « temps réel » est en panne côté agence, l'âge de l'image le montre.
"""
import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from .. import net
from ..cache import ttl_cache

EPIC_API = "https://epic.gsfc.nasa.gov/api/natural"

CAMERAS = [
    {
        "id": "goes19", "group": "Terre", "title": "GOES-19 : la Terre entière",
        "where": "Orbite géostationnaire, 35 786 km, au-dessus de l'Atlantique",
        "what": "Imageur ABI en couleurs naturelles (GeoColor). Une image toutes les 10 minutes : on y voit les ouragans se former.",
        "image": "https://cdn.star.nesdis.noaa.gov/GOES19/ABI/FD/GEOCOLOR/1808x1808.jpg",
        "credit": "NOAA / NESDIS STAR", "norad": "60133",
    },
    {
        "id": "goes18", "group": "Terre", "title": "GOES-18 : la Terre entière",
        "where": "Orbite géostationnaire, 35 786 km, au-dessus du Pacifique",
        "what": "Même imageur que GOES-19, côté Pacifique : Amérique de l'Ouest, Hawaï, Nouvelle-Zélande.",
        "image": "https://cdn.star.nesdis.noaa.gov/GOES18/ABI/FD/GEOCOLOR/1808x1808.jpg",
        "credit": "NOAA / NESDIS STAR", "norad": "51850",
    },
    {
        "id": "epic", "group": "Terre", "title": "DSCOVR / EPIC : la Terre vue de 1,5 million de km",
        "where": "Point de Lagrange L1, entre la Terre et le Soleil",
        "what": "La caméra EPIC voit en permanence la face éclairée de la Terre. Quelques fois par an, la Lune passe devant.",
        "image": None,  # résolue via l'API EPIC
        "credit": "NASA EPIC Team",
    },
    {
        "id": "sdo171", "group": "Soleil", "title": "SDO : la couronne solaire (171 Å)",
        "where": "Orbite géosynchrone inclinée, sonde Solar Dynamics Observatory",
        "what": "Ultraviolet extrême : on voit le plasma à 600 000 °C suivre les boucles du champ magnétique.",
        "image": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0171.jpg",
        "credit": "NASA / SDO / AIA",
    },
    {
        "id": "sdo304", "group": "Soleil", "title": "SDO : la chromosphère (304 Å)",
        "where": "Sonde Solar Dynamics Observatory",
        "what": "Couche à environ 50 000 °C : protubérances et filaments sur le bord du Soleil.",
        "image": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0304.jpg",
        "credit": "NASA / SDO / AIA",
    },
    {
        "id": "sdohmi", "group": "Soleil", "title": "SDO : les taches solaires",
        "where": "Sonde Solar Dynamics Observatory",
        "what": "Lumière visible : le Soleil tel qu'on le verrait avec un filtre, avec ses taches sombres.",
        "image": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_HMIIC.jpg",
        "credit": "NASA / SDO / HMI",
    },
    {
        "id": "lasco_c2", "group": "Soleil", "title": "SOHO / LASCO C2 : la couronne proche",
        "where": "Point de Lagrange L1",
        "what": "Coronographe : un disque cache le Soleil pour voir sa couronne et les éjections de masse coronale.",
        "image": "https://soho.nascom.nasa.gov/data/realtime/c2/1024/latest.jpg",
        "credit": "ESA / NASA SOHO",
    },
    {
        "id": "lasco_c3", "group": "Soleil", "title": "SOHO / LASCO C3 : le champ large",
        "where": "Point de Lagrange L1",
        "what": "Champ de 30 diamètres solaires : on y voit des étoiles, des planètes proches du Soleil et des comètes « rasantes ».",
        "image": "https://soho.nascom.nasa.gov/data/realtime/c3/1024/latest.jpg",
        "credit": "ESA / NASA SOHO",
    },
]

LIVE_VIDEO = {
    "id": "iss", "group": "Direct vidéo", "title": "ISS : caméras extérieures en direct",
    "where": "Station spatiale internationale, ~420 km",
    "what": "Flux vidéo en direct de la chaîne YouTube officielle de la NASA (noir quand la station est dans l'ombre de la Terre).",
    "embed": "https://www.youtube.com/embed/live_stream?channel=UCLA_DiR1FfKNvjuUpBHmylQ&autoplay=1&mute=1",
    "credit": "NASA", "norad": "25544",
}


async def _last_modified(url: str) -> datetime | None:
    r = await net.client().head(url)
    r.raise_for_status()
    value = r.headers.get("last-modified")
    return parsedate_to_datetime(value) if value else None


async def _epic_latest() -> tuple[str | None, datetime | None]:
    items = await net.get_json(EPIC_API)
    if not items:
        return None, None
    last = items[-1]
    taken = datetime.strptime(last["date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    url = f"https://epic.gsfc.nasa.gov/archive/natural/{taken:%Y/%m/%d}/jpg/{last['image']}.jpg"
    return url, taken


async def _resolve(cam: dict) -> dict:
    out = dict(cam)
    try:
        if cam["id"] == "epic":
            out["image"], taken = await _epic_latest()
        else:
            taken = await _last_modified(cam["image"])
    except Exception:
        taken = None
    out["taken"] = taken.isoformat() if taken else None
    if taken:
        age_h = (datetime.now(timezone.utc) - taken).total_seconds() / 3600
        out["age_hours"] = round(age_h, 1)
        # Honnêteté : au-delà de 6 h, on ne parle plus de « temps réel »
        out["fresh"] = age_h <= 6
    return out


@ttl_cache(5 * 60)
async def all_cameras() -> dict:
    cams = await asyncio.gather(*(_resolve(c) for c in CAMERAS))
    return {"live": LIVE_VIDEO, "cameras": list(cams)}
