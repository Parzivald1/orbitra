"""Comètes, astéroïdes et objets interstellaires : données du JPL (NASA).

- SBDB (Small-Body DataBase) : éléments orbitaux de chaque objet
- CAD (Close-Approach Data) : astéroïdes qui frôlent la Terre dans les semaines à venir
"""
import asyncio
import math

from .. import net
from ..cache import ttl_cache

SBDB_URL = "https://ssd-api.jpl.nasa.gov/sbdb.api"
CAD_URL = "https://ssd-api.jpl.nasa.gov/cad.api"

AU_KM = 149_597_870.7
LUNAR_DISTANCE_AU = 384_400 / AU_KM

# Sélection d'objets célèbres (sstr = identifiant de recherche au JPL)
NOTABLE = [
    {"sstr": "1P", "type": "comete", "note": "La plus célèbre des comètes. Revient tous les ~76 ans, prochain retour en 2061. Ses poussières donnent les Orionides et les Êta Aquarides."},
    {"sstr": "2P", "type": "comete", "note": "La comète à la période la plus courte connue (3,3 ans). Mère des Taurides."},
    {"sstr": "8P", "type": "comete", "note": "Comète mère des Ursides."},
    {"sstr": "12P", "type": "comete", "note": "« La comète du diable », visible à l'œil nu au printemps 2024."},
    {"sstr": "21P", "type": "comete", "note": "Comète mère des Draconides, survolée par la sonde ICE en 1985."},
    {"sstr": "55P", "type": "comete", "note": "Comète mère des Léonides, responsable des tempêtes de météores de 1833, 1966 et 2001."},
    {"sstr": "67P", "type": "comete", "note": "Visitée par la sonde Rosetta (ESA). Le robot Philae s'y est posé en 2014 : une première."},
    {"sstr": "109P", "type": "comete", "note": "Comète mère des Perséides. Noyau de 26 km, l'un des plus gros objets à croiser régulièrement l'orbite terrestre."},
    {"sstr": "C/1995 O1", "type": "comete", "note": "Hale-Bopp, visible à l'œil nu pendant 18 mois en 1996-1997. Ne reviendra pas avant ~2 400 ans."},
    {"sstr": "C/2020 F3", "type": "comete", "note": "NEOWISE, la grande comète de l'été 2020."},
    {"sstr": "C/2023 A3", "type": "comete", "note": "Tsuchinshan-ATLAS, spectaculaire en octobre 2024."},
    {"sstr": "1I", "type": "interstellaire", "note": "ʻOumuamua (2017) : premier objet venu d'un autre système stellaire jamais détecté."},
    {"sstr": "2I", "type": "interstellaire", "note": "Borisov (2019) : première comète interstellaire confirmée."},
    {"sstr": "3I", "type": "interstellaire", "note": "3I/ATLAS (2025) : troisième visiteur interstellaire, découvert le 1er juillet 2025."},
    {"sstr": "1", "type": "asteroide", "note": "Cérès, planète naine et plus gros objet de la ceinture d'astéroïdes. Explorée par la sonde Dawn."},
    {"sstr": "4", "type": "asteroide", "note": "Vesta, le deuxième plus gros astéroïde, lui aussi visité par Dawn."},
    {"sstr": "99942", "type": "asteroide", "note": "Apophis : passera à ~32 000 km de la Terre le 13 avril 2029, sous l'orbite des satellites géostationnaires. Aucun risque d'impact."},
    {"sstr": "101955", "type": "asteroide", "note": "Bennu : échantillon ramené sur Terre par la sonde OSIRIS-REx en 2023."},
    {"sstr": "162173", "type": "asteroide", "note": "Ryugu : échantillon ramené par la sonde japonaise Hayabusa2 en 2020."},
    {"sstr": "65803", "type": "asteroide", "note": "Didymos : sa lune Dimorphos a été percutée par la sonde DART en 2022, premier test de défense planétaire."},
    {"sstr": "3200", "type": "asteroide", "note": "Phaéton : un astéroïde qui produit une pluie d'étoiles filantes, les Géminides."},
    {"sstr": "196256", "type": "asteroide", "note": "2003 EH1 : probable comète éteinte, mère des Quadrantides."},
]


def _float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_sbdb(data: dict) -> dict | None:
    if "orbit" not in data:
        return None
    el = {e["name"]: _float(e["value"]) for e in data["orbit"]["elements"]}
    needed = ("e", "q", "i", "om", "w", "tp")
    if any(el.get(k) is None for k in needed):
        return None
    return {
        "name": data["object"]["fullname"],
        "orbit_class": data["object"].get("orbit_class", {}).get("name"),
        "elements": {k: el[k] for k in needed},
        "epoch_jd": _float(data["orbit"].get("epoch")),
    }


# Le JPL refuse une partie des requêtes si on en envoie 20 d'un coup : on se limite à 4.
_jpl_slots = asyncio.Semaphore(4)


@ttl_cache(24 * 3600)
async def body(sstr: str) -> dict | None:
    # Une erreur réseau remonte en exception : ttl_cache ne la met donc PAS en cache
    # (avant, on renvoyait None, qui restait en cache 24 h -> objets manquants).
    last_exc = None
    for attempt in range(3):
        try:
            async with _jpl_slots:
                data = await net.get_json(SBDB_URL, {"sstr": sstr, "full-prec": "1"})
            return parse_sbdb(data)
        except Exception as exc:
            last_exc = exc
            await asyncio.sleep(0.5 * (attempt + 1))
    raise last_exc


async def _safe_body(sstr: str) -> dict | None:
    try:
        return await body(sstr)
    except Exception:
        return None


async def notable() -> list[dict]:
    results = await asyncio.gather(*(_safe_body(n["sstr"]) for n in NOTABLE))
    return [{**n, **r} for n, r in zip(NOTABLE, results) if r]


def diameter_from_h(h: float, albedo: float = 0.14) -> float:
    """Diamètre estimé (km) à partir de la magnitude absolue H.

    D = 1329 / √albédo × 10^(-H/5). L'albédo réel est inconnu pour la plupart
    des petits astéroïdes, d'où une fourchette de taille assez large.
    """
    return 1329 / math.sqrt(albedo) * 10 ** (-h / 5)


@ttl_cache(6 * 3600)
async def close_approaches(days: int = 60, max_ld: float = 10) -> list[dict]:
    data = await net.get_json(CAD_URL, {
        "date-min": "now",
        "date-max": f"+{days}",
        "dist-max": f"{max_ld * LUNAR_DISTANCE_AU:.5f}",
        "sort": "date",
    })
    fields = data.get("fields", [])
    out = []
    for row in data.get("data", []):
        r = dict(zip(fields, row))
        dist_au = float(r["dist"])
        h = _float(r.get("h"))
        out.append({
            "name": r["des"],
            "date": r["cd"],
            "distance_km": round(dist_au * AU_KM),
            "distance_ld": round(dist_au / LUNAR_DISTANCE_AU, 2),
            "speed_kms": round(float(r["v_rel"]), 1),
            "h": h,
            # fourchette : albédo 0,25 (objet clair) à 0,05 (objet sombre)
            "diameter_m": [round(diameter_from_h(h, 0.25) * 1000), round(diameter_from_h(h, 0.05) * 1000)] if h else None,
        })
    return out
