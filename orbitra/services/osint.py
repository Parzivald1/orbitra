"""Dossier OSINT d'un satellite : tout ce qu'on peut savoir à partir de sources ouvertes.

- GCAT (General Catalog of Artificial Space Objects, Jonathan McDowell, Harvard-Smithsonian) :
  constructeur, plateforme, masse, dimensions, programme, type d'utilisateur (civil, commercial,
  militaire, amateur), catégorie de mission, enregistrement à l'ONU. Licence CC-BY.
- SatNOGS DB (Libre Space Foundation, open source) : émetteurs radio, fréquences, modes, état.

GCAT tient en trois fichiers TSV (~25 Mo) : on les télécharge au plus une fois par semaine.
"""
import asyncio
import csv
import time
from functools import lru_cache

from .. import net
from ..cache import ttl_cache
from ..config import CACHE_DIR

GCAT = "https://planet4589.org/space/gcat/tsv"
GCAT_FILES = {"satcat": "cat/satcat.tsv", "psatcat": "cat/psatcat.tsv", "orgs": "tables/orgs.tsv"}
SATNOGS = "https://db.satnogs.org/api"
WEEK = 7 * 24 * 3600

USER_CLASS = {"A": "Amateur / universitaire", "B": "Commercial", "C": "Civil (gouvernemental)", "D": "Militaire"}

CATEGORIES = {
    "COM": "Télécommunications", "IMG": "Imagerie optique", "IMG-R": "Imagerie radar",
    "TECH": "Démonstrateur technologique", "CAL": "Calibration", "SS": "Station spatiale",
    "SIG": "Renseignement électromagnétique (écoute)", "NAV": "Navigation", "SCI": "Science",
    "MET": "Météorologie", "MET-RO": "Météo par radio-occultation", "PLAN": "Exploration planétaire",
    "AST": "Astronomie", "EW": "Alerte avancée (détection de missiles)", "EOSCI": "Science de la Terre",
    "GEOD": "Géodésie", "WEAPON": "Arme / essai antisatellite", "MGRAV": "Microgravité", "BIO": "Biologie",
    "RV": "Rendez-vous / inspection", "INF": "Infrastructure", "NAV/COM": "Navigation et télécoms",
    "COM/MET-RO": "Télécoms et météo",
}

SHAPES = {"Cyl": "Cylindre", "Box": "Boîte", "Pan": "panneaux", "Sphere": "Sphère", "Cone": "Cône",
          "Ant": "antennes", "Irr": "Irrégulière", "Oct": "Octogone", "Hex": "Hexagone"}


# ---------- GCAT ----------

async def _download(name: str) -> None:
    path = CACHE_DIR / f"gcat_{name}.tsv"
    if path.exists() and time.time() - path.stat().st_mtime < WEEK:
        return
    try:
        text = await net.get_text(f"{GCAT}/{GCAT_FILES[name]}")
    except Exception:
        if path.exists():
            return  # on garde l'ancienne copie
        raise
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _rows(name: str):
    with open(CACHE_DIR / f"gcat_{name}.tsv", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        header = [h.lstrip("#").strip() for h in next(reader)]
        for row in reader:
            if row and not row[0].startswith("#"):
                yield {h: v.strip() for h, v in zip(header, row)}


@lru_cache(maxsize=1)
def _index(stamp: float) -> dict:
    """Indexe les trois fichiers par numéro NORAD (le paramètre stamp invalide le cache)."""
    payloads = {r["JCAT"]: r for r in _rows("psatcat")}
    orgs = {r["Code"]: r for r in _rows("orgs")}
    by_norad = {}
    for r in _rows("satcat"):
        if r.get("Satcat", "").isdigit():
            by_norad[str(int(r["Satcat"]))] = (r, payloads.get(r["JCAT"]))
    return {"sats": by_norad, "orgs": orgs}


async def gcat_index() -> dict:
    await asyncio.gather(*(_download(n) for n in GCAT_FILES))
    stamp = (CACHE_DIR / "gcat_satcat.tsv").stat().st_mtime
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(_index, stamp)


def _num(v: str) -> float | None:
    try:
        return float(v.replace("?", "").strip())
    except (ValueError, AttributeError):
        return None


def _org(orgs: dict, codes: str) -> str | None:
    names = []
    for code in (codes or "").replace("/", " ").split():
        o = orgs.get(code.strip("?"))
        if o:
            name = o.get("Name") or o.get("ShortName")
            place = o.get("Location", "").split(",")[-1].split(":")[0].strip()
            names.append(name if "(" in name or not place else f"{name} ({place})")
    return ", ".join(names) or None


def _shape(s: str) -> str | None:
    if not s or s == "-":
        return None
    out = s
    for k, v in SHAPES.items():
        out = out.replace(k, v)
    return " ".join(out.split())


def describe(norad: str, index: dict) -> dict | None:
    found = index["sats"].get(norad)
    if not found:
        return None
    sat, payload = found
    orgs = index["orgs"]
    category_code = (payload or {}).get("Category", "").rstrip("?*")
    user = (payload or {}).get("Class", "")
    mass, dry = _num(sat.get("Mass", "")), _num(sat.get("DryMass", ""))
    dims = {k: _num(sat.get(f, "")) for k, f in (("length", "Length"), ("diameter", "Diameter"), ("span", "Span"))}
    un_state, un_reg = (payload or {}).get("UNState", "-"), (payload or {}).get("UNReg", "-")
    return {
        "jcat": sat.get("JCAT"),
        "name": sat.get("Name"),
        "manufacturer": _org(orgs, sat.get("Manufacturer", "")),
        "owner": _org(orgs, sat.get("Owner", "")),
        "bus": sat.get("Bus") if sat.get("Bus") not in ("", "-") else None,
        "mass_kg": mass if mass else None,
        "dry_mass_kg": dry if dry else None,
        "dimensions_m": {k: v for k, v in dims.items() if v},
        "shape": _shape(sat.get("Shape", "")),
        "program": (payload or {}).get("Program") if (payload or {}).get("Program") not in (None, "", "-") else None,
        "user": [USER_CLASS[c] for c in user if c in USER_CLASS],
        "military": "D" in user,
        "category": CATEGORIES.get(category_code, category_code or None),
        "un_registered": un_reg not in ("", "-"),
        "un_registration": f"{un_state} · {un_reg}" if un_reg not in ("", "-") else None,
        "orbit_class": sat.get("OpOrbit") if sat.get("OpOrbit") not in ("", "-") else None,
        "source": "GCAT, J. McDowell (planet4589.org), CC-BY",
    }


# ---------- SatNOGS ----------

@ttl_cache(24 * 3600)
async def satnogs(norad: str) -> dict | None:
    sats, transmitters = await asyncio.gather(
        net.get_json(f"{SATNOGS}/satellites/", {"norad_cat_id": norad, "format": "json"}),
        net.get_json(f"{SATNOGS}/transmitters/", {"satellite__norad_cat_id": norad, "format": "json"}),
    )
    if not sats:
        return None
    s = sats[0]
    radios = []
    for t in transmitters:
        freq = t.get("downlink_low")
        if not freq:
            continue
        radios.append({
            "label": t.get("description"),
            "mode": t.get("mode"),
            "mhz": round(freq / 1e6, 4),
            "active": t.get("status") == "active",
            "service": t.get("service") if t.get("service") not in (None, "Unknown") else None,
        })
    radios.sort(key=lambda r: (not r["active"], r["mhz"]))
    return {
        "names": s.get("names") or None,
        "status": s.get("status"),
        "countries": s.get("countries") or None,
        "website": s.get("website") or None,
        "page": f"https://db.satnogs.org/satellite/{s.get('sat_id')}",
        "radios": radios,
        "source": "SatNOGS DB (Libre Space Foundation)",
    }


async def dossier(norad: str) -> dict:
    async def quiet(coro):
        try:
            return await coro
        except Exception:
            return None

    async def gcat():
        return describe(norad, await gcat_index())

    g, n = await asyncio.gather(quiet(gcat()), quiet(satnogs(norad)))
    return {"id": norad, "gcat": g, "satnogs": n,
            "sources": [x["source"] for x in (g, n) if x]}
