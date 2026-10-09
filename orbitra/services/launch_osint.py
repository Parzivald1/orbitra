"""Dossier OSINT d'un lancement : tout ce qu'on peut savoir avant et après le décollage.

Sources ouvertes croisées :
- Launch Library 2 (The Space Devs, mode détaillé) : lanceur et ses statistiques, opérateur, pas de tir
  (coordonnées exactes), étage réutilisé et son historique, équipage, clients, orbite visée, liens vidéo,
  et le journal des sources (souvent des NOTAM, avis aux navigants, ou des forums spécialisés)
- Open-Meteo : prévision météo au pas de tir à l'heure du décollage (vent, rafales, nuages, orages)
- CelesTrak SATCAT : après le lancement, la liste des objets réellement mis en orbite (satellites,
  étages, débris) grâce à la désignation internationale, avec leur numéro pour les voir sur le globe

Limite gratuite de Launch Library : 15 requêtes par heure. On ne fait donc que deux appels
(à venir + récents) par heure, et tout le reste est calculé à partir de ces réponses.
"""
import re
from datetime import datetime, timedelta, timezone

from .. import net
from ..cache import ttl_cache

LL2 = "https://ll.thespacedevs.com/2.2.0/launch"
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
SATCAT = "https://celestrak.org/satcat/records.php"


def _g(d, *path):
    for p in path:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    return d


def _stats(o: dict | None) -> dict | None:
    if not o:
        return None
    total = o.get("total_launch_count") or 0
    ok = o.get("successful_launches") or 0
    return {
        "total": total, "successes": ok, "failures": o.get("failed_launches") or 0,
        "success_rate": round(100 * ok / total, 1) if total else None,
        "streak": o.get("consecutive_successful_launches"),
        "landings": o.get("successful_landings"), "landing_attempts": o.get("attempted_landings"),
    }


def _agency(a: dict | None) -> dict | None:
    if not a:
        return None
    return {
        "name": a.get("name"), "abbrev": a.get("abbrev"), "type": a.get("type"), "country": a.get("country_code"),
        "founded": a.get("founding_year"), "leader": a.get("administrator") or None,
        "description": a.get("description"), "wiki": a.get("wiki_url"), "logo": a.get("logo_url"),
        "stats": _stats(a),
    }


def _duration(iso: str | None) -> str | None:
    """« P22DT18H53M » (format ISO 8601) -> « 22 j 18 h »."""
    if not iso:
        return None
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?", iso)
    if not m:
        return None
    d, h, mi = (int(x) if x else 0 for x in m.groups())
    return f"{d} j {h} h" if d else f"{h} h {mi} min"


def _booster(stage: dict) -> dict:
    launcher, landing = stage.get("launcher") or {}, stage.get("landing") or {}
    return {
        "serial": launcher.get("serial_number"),
        "flight_number": stage.get("launcher_flight_number"),
        "flight_proven": launcher.get("flight_proven"),
        "previous_flights": launcher.get("flights"),
        "first_flight": launcher.get("first_launch_date"),
        "status": launcher.get("status"),
        "turnaround": _duration(stage.get("turn_around_time")) if isinstance(stage.get("turn_around_time"), str) else None,
        "landing": {
            "attempt": landing.get("attempt"), "success": landing.get("success"),
            "type": _g(landing, "type", "name"), "location": _g(landing, "location", "name") or _g(landing, "landing_location", "name"),
            "description": landing.get("description"),
        } if landing else None,
    }


# Statuts de Launch Library traduits en français (l'anglais d'origine est remis par le dictionnaire de l'interface)
STATUS_FR = {
    "Go": ("Feu vert pour le lancement", "L'heure de décollage est confirmée par des sources officielles ou fiables."),
    "TBC": ("À confirmer", "Une date est annoncée, mais pas encore confirmée officiellement."),
    "TBD": ("À déterminer", "La date reste incertaine : elle peut encore changer beaucoup."),
    "Success": ("Lancement réussi", "La charge utile a été placée sur l'orbite prévue."),
    "Failure": ("Échec", "Le lancement n'a pas atteint son objectif."),
    "Partial Failure": ("Échec partiel", "La charge utile a été placée sur une orbite différente de celle prévue."),
    "Hold": ("Compte à rebours suspendu", "Le lancement est en attente."),
    "In Flight": ("En vol", "La fusée est en train de voler."),
}


def simplify(l: dict) -> dict:
    cfg = _g(l, "rocket", "configuration") or {}
    pad = l.get("pad") or {}
    mission = l.get("mission") or {}
    sc_stage = _g(l, "rocket", "spacecraft_stage") or {}
    crew = [{"name": _g(c, "astronaut", "name"), "role": _g(c, "role", "role"),
             "agency": _g(c, "astronaut", "agency", "abbrev"), "nationality": _g(c, "astronaut", "nationality")}
            for c in (sc_stage.get("launch_crew") or [])]
    return {
        "id": l.get("id"),
        "name": l.get("name"),
        "net": l.get("net"),
        "net_precision": _g(l, "net_precision", "name"),
        "window_start": l.get("window_start"),
        "window_end": l.get("window_end"),
        "status": STATUS_FR.get(_g(l, "status", "abbrev"), (_g(l, "status", "name"), None))[0],
        "status_abbrev": _g(l, "status", "abbrev"),
        "status_description": STATUS_FR.get(_g(l, "status", "abbrev"), (None, _g(l, "status", "description")))[1],
        "hold_reason": l.get("holdreason") or None, "fail_reason": l.get("failreason") or None,
        "probability": l.get("probability"), "weather_concerns": l.get("weather_concerns"),
        "image": l.get("image"), "infographic": l.get("infographic"),
        "webcast_live": l.get("webcast_live"),
        "provider": _agency(l.get("launch_service_provider")),
        "rocket": {
            "name": cfg.get("full_name") or cfg.get("name"), "family": cfg.get("family"), "variant": cfg.get("variant") or None,
            "description": cfg.get("description"), "reusable": cfg.get("reusable"),
            "length_m": cfg.get("length"), "diameter_m": cfg.get("diameter"), "launch_mass_t": cfg.get("launch_mass"),
            "leo_kg": cfg.get("leo_capacity"), "gto_kg": cfg.get("gto_capacity"), "thrust_kn": cfg.get("to_thrust"),
            "maiden_flight": cfg.get("maiden_flight"), "cost_usd": cfg.get("launch_cost"),
            "image": cfg.get("image_url"), "wiki": cfg.get("wiki_url"),
            "manufacturer": _g(cfg, "manufacturer", "name"), "stats": _stats(cfg),
        },
        "boosters": [_booster(s) for s in (_g(l, "rocket", "launcher_stage") or [])],
        "spacecraft": _g(sc_stage, "spacecraft", "spacecraft_config", "name"),
        "destination": sc_stage.get("destination"),
        "crew": crew,
        "mission": {
            "name": mission.get("name"), "type": mission.get("type"), "description": mission.get("description"),
            "orbit": _g(mission, "orbit", "name"), "orbit_abbrev": _g(mission, "orbit", "abbrev"),
            "orbit_fr": ORBITS.get(_g(mission, "orbit", "abbrev") or "", (None, None))[0],
            "orbit_explained": ORBITS.get(_g(mission, "orbit", "abbrev") or "", (None, None))[1],
            "designator": mission.get("launch_designator"),
            "customers": [a.get("name") for a in (mission.get("agencies") or [])],
        },
        "pad": {
            "name": pad.get("name"), "location": _g(pad, "location", "name"), "country": pad.get("country_code"),
            "lat": float(pad["latitude"]) if pad.get("latitude") else None,
            "lon": float(pad["longitude"]) if pad.get("longitude") else None,
            "launches_from_pad": pad.get("total_launch_count"), "launches_from_site": _g(pad, "location", "total_launch_count"),
            "timezone": _g(pad, "location", "timezone_name"), "wiki": pad.get("wiki_url"),
        },
        "counts": {
            "orbital_ever": l.get("orbital_launch_attempt_count"), "orbital_this_year": l.get("orbital_launch_attempt_count_year"),
            "agency_this_year": l.get("agency_launch_attempt_count_year"), "pad_turnaround": _duration(l.get("pad_turnaround")),
        },
        "videos": [{"title": v.get("title"), "url": v.get("url"), "publisher": v.get("publisher") or v.get("source")}
                   for v in (l.get("vidURLs") or [])][:5],
        "links": [{"title": i.get("title"), "url": i.get("url")} for i in (l.get("infoURLs") or [])][:5],
        "timeline": [{"t": t.get("relative_time"), "event": _g(t, "type", "abbrev") or _g(t, "type", "description")}
                     for t in (l.get("timeline") or [])],
        "patches": [p.get("image_url") for p in (l.get("mission_patches") or []) if p.get("image_url")][:3],
        # le journal des sources : d'où vient l'info (NOTAM, forums spécialisés, communiqués)
        "updates": [{"comment": u.get("comment"), "source": u.get("info_url"), "date": u.get("created_on"),
                     "by": u.get("created_by")} for u in (l.get("updates") or [])][:8],
    }


@ttl_cache(3600)
async def upcoming() -> list[dict]:
    data = await net.get_json(f"{LL2}/upcoming/", {"limit": 20, "mode": "detailed"})
    return [simplify(l) for l in data.get("results", [])]


@ttl_cache(2 * 3600)
async def previous() -> list[dict]:
    data = await net.get_json(f"{LL2}/previous/", {"limit": 15, "mode": "detailed"})
    return [simplify(l) for l in data.get("results", [])]


async def find(launch_id: str) -> dict | None:
    for group in (await upcoming(), await previous()):
        for l in group:
            if l["id"] == launch_id:
                return l
    return None


# ---------- Météo au pas de tir ----------

def weather_verdict(wind: float, gusts: float, cloud: float, rain: float, cape: float) -> dict:
    """Repères indicatifs inspirés des règles de lancement publiques (chaque lanceur a les siennes)."""
    concerns = []
    if gusts and gusts > 55:
        concerns.append("rafales fortes")
    elif wind and wind > 40:
        concerns.append("vent soutenu")
    if cape and cape > 1000:
        concerns.append("risque d'orage (foudre)")
    if rain and rain > 50:
        concerns.append("pluie probable")
    if cloud and cloud > 85:
        concerns.append("couverture nuageuse épaisse")
    level = "défavorable" if len(concerns) >= 2 or "risque d'orage (foudre)" in concerns else "à surveiller" if concerns else "favorable"
    return {"level": level, "concerns": concerns}


@ttl_cache(1800)
async def weather(launch_id: str) -> dict:
    l = await find(launch_id)
    if not l or l["pad"]["lat"] is None or not l["net"]:
        return {"available": False, "reason": "Lancement ou pas de tir inconnu."}
    t0 = datetime.fromisoformat(l["net"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    if t0 < now - timedelta(hours=2) or t0 > now + timedelta(days=15):
        return {"available": False, "reason": "Prévision disponible seulement dans les 15 jours avant le décollage."}
    data = await net.get_json(OPEN_METEO, {
        "latitude": l["pad"]["lat"], "longitude": l["pad"]["lon"],
        "hourly": "temperature_2m,wind_speed_10m,wind_gusts_10m,cloud_cover,precipitation_probability,cape",
        "wind_speed_unit": "kmh", "timezone": "UTC",
        "start_date": t0.date().isoformat(), "end_date": t0.date().isoformat(),
    })
    h = data.get("hourly", {})
    times = h.get("time", [])
    target = t0.strftime("%Y-%m-%dT%H:00")
    i = times.index(target) if target in times else 0
    pick = {k: (h.get(k) or [None])[i] for k in ("temperature_2m", "wind_speed_10m", "wind_gusts_10m", "cloud_cover", "precipitation_probability", "cape")}
    return {
        "available": True, "time": times[i] + "Z" if times else None,
        "temperature_c": pick["temperature_2m"], "wind_kmh": pick["wind_speed_10m"], "gusts_kmh": pick["wind_gusts_10m"],
        "cloud_pct": pick["cloud_cover"], "rain_pct": pick["precipitation_probability"], "cape": pick["cape"],
        "verdict": weather_verdict(pick["wind_speed_10m"] or 0, pick["wind_gusts_10m"] or 0, pick["cloud_cover"] or 0,
                                   pick["precipitation_probability"] or 0, pick["cape"] or 0),
        "source": "Open-Meteo",
    }


# ---------- Ce que le lancement a mis en orbite ----------

# Où va la fusée : explication de chaque type d'orbite visé
ORBITS = {
    "LEO": ("Orbite basse", "Entre 200 et 2 000 km d'altitude, un tour de Terre en 90 minutes environ. C'est là que vivent l'ISS, Starlink et la plupart des satellites d'observation."),
    "SSO": ("Orbite héliosynchrone", "Orbite polaire vers 500-800 km, calée sur le Soleil : le satellite repasse au-dessus de chaque endroit toujours à la même heure solaire. Idéale pour comparer des images d'un jour à l'autre."),
    "PO": ("Orbite polaire", "Passe au-dessus des deux pôles : avec la rotation de la Terre en dessous, le satellite finit par survoler toute la planète."),
    "GTO": ("Transfert géostationnaire", "Orbite très allongée (200 km au plus bas, 36 000 km au plus haut). Le satellite utilise ensuite son propre moteur pour se placer en orbite géostationnaire."),
    "GEO": ("Orbite géostationnaire", "À 35 786 km au-dessus de l'équateur, le satellite tourne à la même vitesse que la Terre : il paraît immobile dans le ciel. Télécoms et météo."),
    "MEO": ("Orbite moyenne", "Entre 2 000 et 35 000 km. C'est l'orbite des systèmes de navigation : GPS, Galileo, GLONASS, BeiDou."),
    "HEO": ("Orbite très elliptique", "Orbite très allongée qui permet de rester longtemps au-dessus d'une région (ex. orbite Molniya pour la Russie)."),
    "TLI": ("Vers la Lune", "Injection translunaire : la fusée quitte l'orbite terrestre pour rejoindre la Lune, à environ 384 000 km."),
    "Lunar": ("Vers la Lune", "Mise en orbite autour de la Lune."),
    "Mars": ("Vers Mars", "Trajectoire interplanétaire vers Mars : 6 à 9 mois de voyage. Possible seulement tous les 26 mois, quand la Terre et Mars sont bien placées."),
    "Helio-N": ("Orbite autour du Soleil", "Trajectoire héliocentrique : la sonde quitte l'attraction de la Terre pour tourner autour du Soleil."),
    "Sub": ("Vol suborbital", "La fusée monte dans l'espace puis retombe sans faire le tour de la Terre."),
    "L1": ("Point de Lagrange L1", "À 1,5 million de km vers le Soleil, un point d'équilibre où une sonde peut rester entre la Terre et le Soleil."),
    "L2": ("Point de Lagrange L2", "À 1,5 million de km à l'opposé du Soleil, là où se trouve le télescope James Webb."),
}

TYPES = {"PAY": "Satellite", "R/B": "Étage de fusée", "DEB": "Débris", "UNK": "Inconnu"}
GCAT_LAUNCHES = "https://planet4589.org/space/gcat/tsv/launch/launch.tsv"


@ttl_cache(12 * 3600)
async def _gcat_recent_launches() -> list[tuple[float, str]]:
    """(jour julien, désignation) des derniers lancements orbitaux du catalogue de J. McDowell."""
    text = await net.get_text(GCAT_LAUNCHES)
    out = []
    for line in text.splitlines()[-3000:]:  # les plus récents sont à la fin
        cols = line.split("\t")
        tag = cols[0].strip() if cols else ""
        if re.fullmatch(r"\d{4}-\d{3}", tag):  # les tirs suborbitaux et missiles ont un « S » : exclus
            try:
                out.append((float(cols[1]), tag))
            except (ValueError, IndexError):
                pass
    return out


async def designator_for(net_iso: str) -> str | None:
    """Launch Library ne donne pas toujours la désignation : on la retrouve par l'heure du décollage."""
    t0 = datetime.fromisoformat(net_iso.replace("Z", "+00:00"))
    jd = 2440587.5 + t0.timestamp() / 86400
    best = min(((abs(j - jd), tag) for j, tag in await _gcat_recent_launches()), default=None)
    return best[1] if best and best[0] < 30 / 1440 else None  # tolérance : 30 minutes


@ttl_cache(6 * 3600)
async def objects(launch_id: str) -> dict:
    l = await find(launch_id)
    designator = (l or {}).get("mission", {}).get("designator")
    if l and not designator and l.get("net") and l.get("status_abbrev") in ("Success", "Partial Failure", "Failure"):
        try:
            designator = await designator_for(l["net"])
        except Exception:
            designator = None
    if not designator or not re.fullmatch(r"\d{4}-\d{3}", designator):
        return {"available": False, "reason": "Pas encore de désignation internationale (elle est attribuée après le lancement)."}
    rows = await net.get_json(SATCAT, {"INTDES": designator, "FORMAT": "json"})
    rows = rows if isinstance(rows, list) else []
    return {
        "available": True, "designator": designator, "count": len(rows),
        "objects": [{"norad": str(r.get("NORAD_CAT_ID")), "name": r.get("OBJECT_NAME"), "type": TYPES.get(r.get("OBJECT_TYPE"), r.get("OBJECT_TYPE")),
                     "decayed": r.get("DECAY_DATE") or None, "perigee": r.get("PERIGEE"), "apogee": r.get("APOGEE"),
                     "inclination": r.get("INCLINATION")} for r in rows],
        "source": "CelesTrak SATCAT",
    }
