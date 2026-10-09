"""API Orbitra (FastAPI) + service de l'interface web.

Lancer en local :  uvicorn orbitra.main:app --reload
Documentation interactive de l'API : http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import astronomy
import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from . import __version__, net
from .astro import eclipses, meteors, passes, sky, solarsystem
from .astro.timeutil import to_astro, to_jd, utcnow
from .config import DEFAULT_ALT_M, DEFAULT_LAT, DEFAULT_LON, WEB_DIR
from .services import discoveries, launches, satellites, satinfo, smallbodies


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
async def get_satellite_info(norad_id: str):
    """Fiche complète : mission, lancement, statut, ce qu'il récolte, fin de mission."""
    sat = await satellites.get_tle(norad_id)
    if not sat:
        raise HTTPException(404, f"Satellite {norad_id} introuvable")
    return await satinfo.info(norad_id, sat["name"])


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
async def get_launches():
    return await launches.upcoming()


@app.get("/api/exoplanets")
async def get_exoplanets():
    return await discoveries.exoplanets()


@app.get("/api/news")
async def get_news():
    return await discoveries.news()


# L'interface web est servie à la racine (doit rester en dernier)
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
