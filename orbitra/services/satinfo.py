"""Fiche d'identité d'un objet en orbite : pourquoi il est là, depuis quand, ce qu'il fait.

Trois sources croisées, de la plus complète à la plus générale :
1. CelesTrak SATCAT  : registre officiel de TOUS les objets catalogués
                       (date et site de lancement, pays, statut, rentrée atmosphérique)
2. Wikidata + Wikipédia (fr) : mission, opérateur, fin de mission, photo, résumé
                       (uniquement pour les objets assez connus pour avoir une fiche)
3. Familles (rédigées à la main) : ce que fait un Starlink, un GPS, un Sentinel...
                       pour que même un satellite anonyme ait une explication
"""
import asyncio
from datetime import date
from urllib.parse import quote, unquote

from .. import net
from ..cache import ttl_cache

SATCAT_URL = "https://celestrak.org/satcat/records.php"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WIKIPEDIA_SUMMARY = "https://fr.wikipedia.org/api/rest_v1/page/summary/"

OBJECT_TYPES = {"PAY": "Satellite (charge utile)", "R/B": "Étage de fusée", "DEB": "Débris", "UNK": "Inconnu"}

STATUS = {
    "+": "En service", "-": "Hors service", "P": "Partiellement en service", "B": "En réserve (backup)",
    "S": "Satellite de rechange", "X": "Mission prolongée", "D": "Rentré dans l'atmosphère", "?": "Inconnu",
}

OWNERS = {
    "US": "États-Unis", "PRC": "Chine", "CIS": "Russie / ex-URSS", "FR": "France", "ESA": "Agence spatiale européenne",
    "EUME": "EUMETSAT (Europe)", "EUTE": "Eutelsat (Europe)", "ISS": "Station spatiale internationale (coopération)",
    "JPN": "Japon", "IND": "Inde", "UK": "Royaume-Uni", "GER": "Allemagne", "IT": "Italie", "CA": "Canada",
    "SKOR": "Corée du Sud", "NKOR": "Corée du Nord", "ISRA": "Israël", "IRAN": "Iran", "BRAZ": "Brésil",
    "AUS": "Australie", "SPN": "Espagne", "LUXE": "Luxembourg", "SES": "SES (Luxembourg)", "O3B": "O3b / SES",
    "GLOB": "Globalstar", "ORB": "Orbcomm", "IRID": "Iridium", "ITSO": "Intelsat", "UAE": "Émirats arabes unis",
    "SAUD": "Arabie saoudite", "TURK": "Turquie", "ARGN": "Argentine", "MEX": "Mexique", "INDO": "Indonésie",
    "TWN": "Taïwan", "NOR": "Norvège", "SWED": "Suède", "FIN": "Finlande", "NETH": "Pays-Bas", "BEL": "Belgique",
    "SWTZ": "Suisse", "POL": "Pologne", "UKR": "Ukraine", "KAZ": "Kazakhstan", "THAI": "Thaïlande",
    "SING": "Singapour", "PAKI": "Pakistan", "EGYP": "Égypte", "NZ": "Nouvelle-Zélande", "AB": "Arabsat",
}

# Codes officiels CelesTrak (https://celestrak.org/satcat/launchsites.php).
# Correctif : la première version avait été écrite de mémoire et contenait 5 codes faux.
LAUNCH_SITES = {
    "AFETR": "Cap Canaveral / Kennedy (Floride, États-Unis)", "AFWTR": "Vandenberg (Californie, États-Unis)",
    "ANDSP": "Andøya (Norvège)", "ALCLC": "Alcântara (Brésil)", "BOS": "Bowen (Queensland, Australie)",
    "CAS": "Espace aérien des Canaries (lancement depuis un avion)", "DLS": "Dombarovsky (Russie)",
    "ERAS": "Espace aérien Est des États-Unis (lancement depuis un avion)", "FRGUI": "Kourou (Guyane française)",
    "HGSTR": "Hammaguir (Algérie)", "JJSLA": "Zone de lancement en mer de Jeju (Corée du Sud)",
    "JSC": "Jiuquan (Chine)", "KODAK": "Kodiak (Alaska, États-Unis)", "KSCUT": "Uchinoura (Japon)",
    "KWAJ": "Atoll de Kwajalein (Îles Marshall)", "KYMSC": "Kapoustine Iar (Russie)", "NSC": "Naro (Corée du Sud)",
    "PLMSC": "Plessetsk (Russie)", "RLLB": "Mahia (Nouvelle-Zélande, Rocket Lab)",
    "SCSLA": "Zone de lancement en mer de Chine méridionale", "SEAL": "Plateforme Sea Launch (en mer)",
    "SEMLS": "Semnan (Iran)", "SMTS": "Shahroud (Iran)", "SNMLP": "Plateforme San Marco (Kenya)",
    "SPKII": "Spaceport Kii (Japon)", "SRILR": "Sriharikota (Inde)", "STARB": "Starbase (Texas, États-Unis)",
    "SUBL": "Sous-marin", "SVOBO": "Svobodny (Russie)", "TAISC": "Taiyuan (Chine)", "TANSC": "Tanegashima (Japon)",
    "TYMSC": "Baïkonour (Kazakhstan)", "UNK": "Inconnu", "VOSTO": "Vostotchny (Russie)",
    "WLPIS": "Wallops Island (Virginie, États-Unis)", "WOMRA": "Woomera (Australie)",
    "WRAS": "Espace aérien Ouest des États-Unis (lancement depuis un avion)", "WSC": "Wenchang (Chine)",
    "XICLF": "Xichang (Chine)", "YAVNE": "Yavne (Israël)", "YSLA": "Zone de lancement en mer Jaune (Chine)",
    "YUN": "Sohae (Corée du Nord)",
}

# Familles reconnues par le nom : mission et données recueillies, en français
FAMILIES = [
    ("STARLINK", {
        "mission": "Internet haut débit par satellite (SpaceX). Plusieurs milliers de satellites en orbite basse forment un maillage mondial, reliés entre eux par lasers.",
        "collects": "Ne récolte pas de données scientifiques : il relaie le trafic Internet entre les antennes au sol.",
        "lifetime": "Durée de vie d'environ 5 ans, puis désorbitation volontaire : il brûle dans l'atmosphère.",
    }),
    ("ONEWEB", {
        "mission": "Internet par satellite (Eutelsat OneWeb), orbite à ~1 200 km, surtout pour les entreprises, avions et bateaux.",
        "collects": "Relais de communications, pas de mesures scientifiques.",
    }),
    ("KUIPER", {"mission": "Constellation Internet d'Amazon (projet Kuiper), concurrente de Starlink.", "collects": "Relais de communications."}),
    ("IRIDIUM", {
        "mission": "Téléphonie et messagerie satellite partout sur Terre, pôles compris (66 satellites).",
        "collects": "Communications ; porte aussi des récepteurs ADS-B qui suivent les avions au-dessus des océans.",
    }),
    ("GLOBALSTAR", {"mission": "Téléphonie satellite et balises de détresse (SOS par satellite des iPhone).", "collects": "Relais de communications."}),
    ("ORBCOMM", {"mission": "Messagerie pour objets connectés (suivi de conteneurs, de bateaux, d'engins).", "collects": "Messages courts et signaux AIS des navires."}),
    ("NAVSTAR", {
        "mission": "Système GPS américain : 31 satellites à 20 200 km qui donnent la position de n'importe quel récepteur sur Terre.",
        "collects": "Émet en continu l'heure exacte de ses horloges atomiques ; le récepteur calcule sa position en comparant les temps de trajet de 4 signaux ou plus.",
    }),
    ("GPS", {
        "mission": "Système GPS américain (positionnement mondial).",
        "collects": "Signaux horaires d'horloges atomiques pour le calcul de position.",
    }),
    ("GSAT0", {
        "mission": "Galileo, le GPS européen, plus précis que le GPS américain (au mètre près pour le grand public).",
        "collects": "Signaux de navigation d'horloges atomiques ; relaie aussi les balises de détresse (service SAR).",
    }),
    ("GALILEO", {"mission": "Galileo, le système de navigation européen.", "collects": "Signaux de navigation."}),
    ("COSMOS 2", {"mission": "Satellite russe de la série Cosmos (navigation GLONASS, militaire ou scientifique selon le numéro).", "collects": "Variable selon la mission."}),
    ("GLONASS", {"mission": "GLONASS, le système de navigation russe.", "collects": "Signaux de navigation."}),
    ("BEIDOU", {"mission": "BeiDou, le système de navigation chinois (45+ satellites).", "collects": "Signaux de navigation et messages courts."}),
    ("SENTINEL-1", {
        "mission": "Copernicus (UE/ESA) : radar qui photographie la Terre de jour comme de nuit, à travers les nuages.",
        "collects": "Images radar : glissements de terrain, inondations, glaces de mer, déformation du sol après un séisme.",
    }),
    ("SENTINEL-2", {
        "mission": "Copernicus (UE/ESA) : imagerie optique haute résolution des terres émergées.",
        "collects": "Images en 13 bandes de couleur (dont l'infrarouge) : état des cultures, forêts, feux, urbanisation.",
    }),
    ("SENTINEL-3", {
        "mission": "Copernicus (UE/ESA) : surveillance des océans et du climat.",
        "collects": "Température et couleur des océans, hauteur des mers, feux de forêt.",
    }),
    ("SENTINEL-5P", {
        "mission": "Copernicus (UE/ESA) : qualité de l'air et composition de l'atmosphère.",
        "collects": "Instrument TROPOMI : mesure chaque jour le dioxyde d'azote (NO₂), l'ozone (O₃), le méthane (CH₄), le monoxyde de carbone (CO), le dioxyde de soufre (SO₂) et les aérosols, en analysant la lumière du Soleil réfléchie par la Terre (spectroscopie d'absorption).",
    }),
    ("SENTINEL-6", {"mission": "Copernicus : mesure du niveau des océans au centimètre près.", "collects": "Altimétrie radar : montée du niveau de la mer."}),
    ("NOAA", {
        "mission": "Satellites météo américains (NOAA) en orbite polaire.",
        "collects": "Images des nuages, températures et humidité de l'atmosphère pour les prévisions météo.",
    }),
    ("METOP", {"mission": "Satellites météo européens (EUMETSAT) en orbite polaire.", "collects": "Profils de température et d'humidité, vents à la surface des océans, ozone."}),
    ("METEOSAT", {"mission": "Satellites météo européens géostationnaires, fixes au-dessus de l'Afrique et de l'Europe.", "collects": "Une image complète du disque terrestre toutes les 10 à 15 minutes (les images de la météo à la télé)."}),
    ("GOES", {"mission": "Satellites météo géostationnaires américains.", "collects": "Images des nuages en continu, éclairs, éruptions solaires."}),
    ("FENGYUN", {"mission": "Satellites météo chinois.", "collects": "Images des nuages et profils atmosphériques."}),
    ("LANDSAT", {"mission": "Programme américain d'observation des terres, depuis 1972 : la plus longue série d'images de la Terre.", "collects": "Images multispectrales : évolution des forêts, villes, glaciers depuis 50 ans."}),
    ("FLOCK", {"mission": "Nanosatellites Planet (format CubeSat) qui photographient toute la Terre chaque jour.", "collects": "Images de 3 à 5 m de résolution."}),
    ("SKYSAT", {"mission": "Satellites d'imagerie haute résolution de Planet.", "collects": "Images et vidéos à ~50 cm de résolution."}),
    ("TIANHE", {"mission": "Module central de la station spatiale chinoise Tiangong.", "collects": "Expériences scientifiques en microgravité ; habité par 3 taïkonautes."}),
    ("CSS", {"mission": "Station spatiale chinoise Tiangong.", "collects": "Expériences scientifiques en microgravité."}),
    ("ISS", {
        "mission": "Station spatiale internationale (États-Unis, Russie, Europe, Japon, Canada), habitée en permanence depuis novembre 2000.",
        "collects": "Laboratoire en microgravité : biologie, médecine, physique des fluides, matériaux, observation de la Terre. Les Français Thomas Pesquet (2016-2017 et 2021) et Sophie Adenot (2026) y ont séjourné.",
        "lifetime": "Fin de vie prévue vers 2030 : elle sera désorbitée au-dessus du Pacifique par un remorqueur de SpaceX.",
    }),
    ("HST", {
        "mission": "Télescope spatial Hubble (NASA/ESA), lancé en 1990.",
        "collects": "Images et spectres dans le visible, l'ultraviolet et le proche infrarouge : âge de l'Univers, expansion accélérée, atmosphères d'exoplanètes.",
    }),
]

DEBRIS_TEXT = {
    "mission": "Débris spatial : morceau d'un satellite ou d'une fusée, sans aucune fonction.",
    "collects": "Rien. C'est un danger pour les satellites actifs : à 7-8 km/s, même un fragment de quelques centimètres peut détruire un satellite.",
}
ROCKET_BODY_TEXT = {
    "mission": "Étage de fusée resté en orbite après avoir largué son satellite.",
    "collects": "Rien. Il finira par retomber et brûler dans l'atmosphère, plus ou moins vite selon son altitude.",
}


def family(name: str, object_type: str | None) -> dict | None:
    upper = name.upper()
    if object_type == "DEB" or " DEB" in upper:
        return DEBRIS_TEXT
    if object_type == "R/B" or " R/B" in upper:
        return ROCKET_BODY_TEXT
    for prefix, info in FAMILIES:
        if upper.startswith(prefix) or f"({prefix}" in upper:
            return info
    return None


def size_from_rcs(rcs: float | None) -> str | None:
    """Section efficace radar (m²) -> taille approximative."""
    if rcs is None:
        return None
    if rcs < 0.1:
        return "Petit (moins de 30 cm environ)"
    if rcs < 1:
        return "Moyen (environ 30 cm à 1 m)"
    if rcs < 10:
        return "Grand (1 à 3 m)"
    return "Très grand (plusieurs mètres)"


def years_since(iso_date: str | None) -> float | None:
    try:
        d = date.fromisoformat(iso_date)
    except (TypeError, ValueError):
        return None
    return round((date.today() - d).days / 365.25, 1)


@ttl_cache(24 * 3600)
async def satcat(norad_id: str) -> dict | None:
    data = await net.get_json(SATCAT_URL, {"CATNR": norad_id, "FORMAT": "json"})
    return data[0] if isinstance(data, list) and data else None


@ttl_cache(7 * 24 * 3600)
async def wikidata(norad_id: str) -> dict | None:
    if not norad_id.isdigit():  # protège la requête SPARQL (le numéro est injecté dedans)
        return None
    query = f"""
    SELECT ?item ?itemLabel ?itemDescription ?article ?launch ?end ?decay ?operatorLabel ?useLabel ?image WHERE {{
      ?item wdt:P377 "{int(norad_id)}".
      OPTIONAL {{ ?item wdt:P619 ?launch }}
      OPTIONAL {{ ?item wdt:P582 ?end }}
      OPTIONAL {{ ?item wdt:P621 ?decay }}
      OPTIONAL {{ ?item wdt:P137 ?operator }}
      OPTIONAL {{ ?item wdt:P366 ?use }}
      OPTIONAL {{ ?item wdt:P18 ?image }}
      OPTIONAL {{ ?article schema:about ?item; schema:isPartOf <https://fr.wikipedia.org/> }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "fr,en". }}
    }} LIMIT 20"""
    r = await net.client().get(WIKIDATA_SPARQL, params={"query": query},
                               headers={"Accept": "application/sparql-results+json"})
    r.raise_for_status()
    rows = r.json()["results"]["bindings"]
    if not rows:
        return None

    def values(key):
        seen = []
        for row in rows:
            v = row.get(key, {}).get("value")
            if v and v not in seen:
                seen.append(v)
        return seen

    first = lambda key: (values(key) or [None])[0]
    return {
        "wikidata": first("item"),
        "label": first("itemLabel"),
        "description": first("itemDescription"),
        "article": first("article"),
        "launch": (first("launch") or "")[:10] or None,
        "mission_end": (first("end") or first("decay") or "")[:10] or None,
        "operators": values("operatorLabel"),
        "uses": values("useLabel"),
        "image": first("image"),
    }


@ttl_cache(7 * 24 * 3600)
async def wikipedia_summary(article_url: str) -> dict | None:
    title = unquote(article_url.rsplit("/wiki/", 1)[-1])
    data = await net.get_json(WIKIPEDIA_SUMMARY + quote(title, safe=""))
    return {
        "title": data.get("title"),
        "extract": data.get("extract"),
        "thumbnail": (data.get("thumbnail") or {}).get("source"),
        "url": (data.get("content_urls") or {}).get("desktop", {}).get("page", article_url),
    }


async def _quiet(coro):
    try:
        return await coro
    except Exception:
        return None


async def info(norad_id: str, name: str) -> dict:
    cat, wd = await asyncio.gather(_quiet(satcat(norad_id)), _quiet(wikidata(norad_id)))
    wiki = await _quiet(wikipedia_summary(wd["article"])) if wd and wd.get("article") else None

    obj_type = cat.get("OBJECT_TYPE") if cat else None
    launch = (cat or {}).get("LAUNCH_DATE") or (wd or {}).get("launch")
    decay = (cat or {}).get("DECAY_DATE") or None
    owner = (cat or {}).get("OWNER")
    site = (cat or {}).get("LAUNCH_SITE")
    rcs = (cat or {}).get("RCS")

    return {
        "id": norad_id,
        "name": name,
        "object_id": (cat or {}).get("OBJECT_ID"),
        "type": OBJECT_TYPES.get(obj_type, obj_type),
        "status": STATUS.get((cat or {}).get("OPS_STATUS_CODE") or "?", "Inconnu") if cat else None,
        "owner": OWNERS.get(owner, owner),
        "launch_date": launch,
        "launch_site": LAUNCH_SITES.get(site, site),
        "years_in_orbit": years_since(launch),
        "decay_date": decay,
        "mission_end": (wd or {}).get("mission_end"),
        "size": size_from_rcs(rcs),
        "family": family(name, obj_type),
        "wikidata": wd,
        "wikipedia": wiki,
        "sources": [s for s, ok in (("CelesTrak SATCAT", cat), ("Wikidata", wd), ("Wikipédia", wiki)) if ok],
    }
