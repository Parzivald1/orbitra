"""API Orbitra (FastAPI) + service de l'interface web.

Lancer en local :  uvicorn orbitra.main:app --reload
Documentation interactive de l'API : http://127.0.0.1:8000/docs
"""
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import astronomy
import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from . import __version__, net
from .astro import eclipses, meteors, passes, sky, solarsystem
from .astro.timeutil import to_astro, to_jd, utcnow
from .config import DEFAULT_ALT_M, DEFAULT_LAT, DEFAULT_LON, WEB_DIR
from .services import atmosphere, discoveries, launch_osint, gallery, isscam, launches, osint, satellites, satinfo, smallbodies, spacecams


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await net.close()


app = FastAPI(
    title="Orbitra",
    version=__version__,
    description="Tout ce qui se passe au-dessus de nos têtes : satellites, éclipses, comètes, lancements, découvertes.",
    lifespan=lifespan,
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.exception_handler(httpx.HTTPError)
async def upstream_error(_request: Request, exc: httpx.HTTPError):
    return JSONResponse(status_code=502, content={"detail": f"Source externe indisponible ({type(exc).__name__})"})


Lat = Query(DEFAULT_LAT, ge=-90, le=90, description="Latitude (°)")
Lon = Query(DEFAULT_LON, ge=-180, le=180, description="Longitude (°)")
Alt = Query(DEFAULT_ALT_M, ge=-500, le=9000, description="Altitude (m)")


@app.get("/api/config")
async def get_config():
    """Réglages publics pour l'interface (la clé Cesium ion est faite pour être utilisée dans le navigateur)."""
    return {"cesium_ion_token": os.environ.get("CESIUM_ION_TOKEN") or None}


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": __version__, "time": utcnow().isoformat(timespec="seconds")}


# ---------- Orbite terrestre ----------

@app.get("/api/satellites")
async def get_satellites():
    try:
        return await satellites.catalog()
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))


@app.get("/api/satellites/{norad_id}/info")
async def get_satellite_info(norad_id: str, lang: str = Query("fr", pattern="^[a-z]{2}$")):
    """Fiche complète : mission, lancement, statut, ce qu'il récolte, fin de mission."""
    sat = await satellites.get_tle(norad_id)
    if not sat:
        raise HTTPException(404, f"Satellite {norad_id} introuvable")
    return await satinfo.info(norad_id, sat["name"], lang)


@app.get("/api/satellites/{norad_id}/osint")
async def get_satellite_osint(norad_id: str):
    """Dossier OSINT : constructeur, masse, programme, usage civil ou militaire, fréquences radio."""
    if not norad_id.isdigit():
        raise HTTPException(422, "Numéro NORAD invalide")
    return await osint.dossier(str(int(norad_id)))


@app.get("/api/satellites/{norad_id}/passes")
async def get_passes(norad_id: str, lat: float = Lat, lon: float = Lon, alt: float = Alt,
                     hours: float = Query(72, gt=0, le=240), min_elevation: float = Query(10, ge=0, le=90)):
    sat = await satellites.get_tle(norad_id)
    if not sat:
        raise HTTPException(404, f"Satellite {norad_id} introuvable")
    result = await run_in_threadpool(passes.find_passes, sat["l1"], sat["l2"], lat, lon, alt,
                                     utcnow(), hours, min_elevation)
    return {"satellite": sat["name"], "id": norad_id, "passes": result}


# ---------- Ciel et événements ----------

@app.get("/api/sky")
async def get_sky(lat: float = Lat, lon: float = Lon, alt: float = Alt):
    return await run_in_threadpool(sky.tonight, lat, lon, alt, utcnow())


@app.get("/api/eclipses")
async def get_eclipses(lat: float = Lat, lon: float = Lon, alt: float = Alt):
    observer = astronomy.Observer(lat, lon, alt)
    return await run_in_threadpool(eclipses.summary, to_astro(utcnow()), observer)


@app.get("/api/meteors")
async def get_meteors():
    return meteors.upcoming()


@app.get("/api/close-approaches")
async def get_close_approaches():
    return await smallbodies.close_approaches()


# ---------- Système solaire ----------

@app.get("/api/solar-system/orbits")
async def get_orbits():
    bodies = await smallbodies.notable()
    return {
        "planets": solarsystem.planet_orbits(),
        "small_bodies": solarsystem.small_body_orbits(bodies),
    }


@app.get("/api/solar-system/positions")
async def get_positions(date: datetime | None = Query(None, description="Date ISO 8601 (défaut : maintenant)")):
    when = date or utcnow()
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    if not 1600 <= when.year <= 2400:
        raise HTTPException(422, "Date hors de la plage 1600-2400")
    bodies = await smallbodies.notable()
    return solarsystem.positions(to_jd(when), bodies)


# ---------- Lancements et découvertes ----------

@app.get("/api/launches")
async def get_launches(when: str = Query("upcoming", pattern="^(upcoming|previous)$")):
    """Lancements à venir ou récents, avec le dossier OSINT complet de chacun."""
    return await (launch_osint.upcoming() if when == "upcoming" else launch_osint.previous())


@app.get("/api/launches/{launch_id}/weather")
async def get_launch_weather(launch_id: str):
    """Météo prévue au pas de tir à l'heure du décollage (Open-Meteo)."""
    if not re.fullmatch(r"[0-9a-f-]{36}", launch_id):
        raise HTTPException(422, "Identifiant invalide")
    return await launch_osint.weather(launch_id)


@app.get("/api/launches/{launch_id}/objects")
async def get_launch_objects(launch_id: str):
    """Objets mis en orbite par ce lancement (CelesTrak SATCAT)."""
    if not re.fullmatch(r"[0-9a-f-]{36}", launch_id):
        raise HTTPException(422, "Identifiant invalide")
    return await launch_osint.objects(launch_id)


@app.get("/api/exoplanets")
async def get_exoplanets():
    return await discoveries.exoplanets()


@app.get("/api/atmosphere/layers")
async def get_atmosphere_layers():
    """Couches de pollution mesurées par satellite, avec leurs dates disponibles."""
    return await atmosphere.layers()


@app.get("/api/atmosphere/tile/{key}/{date}/{z}/{y}/{x}.png")
async def get_atmosphere_tile(key: str, date: str, z: int, y: int, x: int, days: int = Query(7, ge=1, le=14)):
    """Tuile moyennée sur plusieurs jours (calculée ici à partir des tuiles quotidiennes de la NASA)."""
    import re as _re
    if key not in atmosphere.BY_KEY or not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) or not 0 <= z <= atmosphere.ZOOM \
            or not (0 <= x < 2 ** z and 0 <= y < 2 ** z):
        raise HTTPException(422, "Paramètres de tuile invalides")
    png = await atmosphere.composite_tile(key, date, z, y, x, days)
    return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=21600"})


@app.get("/api/atmosphere/value")
async def get_atmosphere_value(key: str = Query(..., pattern="^(no2|so2|co|ch4|aod|o3)$"),
                               date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
                               lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180)):
    """Valeur mesurée par le satellite à un endroit précis (lue dans la tuile + table de couleurs NASA)."""
    return await atmosphere.value_at(key, date, lat, lon)


@app.get("/api/cameras")
async def get_cameras():
    """Dernières images réelles des caméras spatiales (Terre, Soleil) + direct de l'ISS."""
    return await spacecams.all_cameras()


@app.get("/api/iss/photos")
async def get_iss_photos():
    """Dernières vraies photos prises par l'équipage de l'ISS."""
    return {"photos": await isscam.crew_photos(), "sequences_enabled": isscam.eol_key() is not None,
            "days": isscam.recent_days()}


@app.get("/api/iss/sequences")
async def get_iss_sequences(day: str = Query(..., pattern=r"^\d{8}$", description="Date AAAAMMJJ")):
    """Séquences de photos consécutives de l'ISS (film du trajet). Nécessite EOL_API_KEY."""
    try:
        return await isscam.sequences(day)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))


@app.get("/api/gallery")
async def get_gallery():
    """Clichés remarquables de la Lune et des planètes, enregistrés automatiquement."""
    return await gallery.gallery()


@app.get("/api/news")
async def get_news():
    return await discoveries.news()


# L'interface web est servie à la racine (doit rester en dernier)
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
