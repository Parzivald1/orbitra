<div align="center">

<img src="web/icons/icon-192.png" width="88" alt="Orbitra logo">

# Orbitra

Everything happening above our heads, in real time.

[![Tests](https://github.com/Parzivald1/orbitra/actions/workflows/ci.yml/badge.svg)](https://github.com/Parzivald1/orbitra/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

[Français](README.md) · **English**

![The globe with the 18,000 tracked objects](docs/screenshots/orbite.png)

</div>

> The app itself is in French for now (an English version is on the roadmap). The code comments are in French too,
> but the variable and function names are in English.

## Why I built this

One evening I saw a bright dot crossing the sky without blinking. I wanted to know what it was, what it was for,
and who had launched it. I couldn't find a single app that answered all of that in one place and also explained
how it works. So I built one.

Orbitra tracks more than 18,000 objects in orbit (satellites, debris, space stations), computes eclipses and meteor
showers, shows where the comets are, and displays real images taken from space. My rule was to **compute** as much
as possible myself from the raw data of NASA, ESA or JPL instead of copying ready-made lists. That's where I learned the most.

## What you can do with it

**The globe.** A high-definition Earth that you can zoom into down to street level. Satellite positions are
recomputed continuously in the browser. Click on a satellite and you get its mission, what it measures, how long
it has been up there, where it launched from, when its mission ends, and its next passes over your location.
Fly close to the ISS, Hubble or Landsat and you see the real spacecraft in 3D (official NASA models).

![The ISS in 3D above the Amazon](docs/screenshots/iss-3d.png)

**The OSINT file.** For each satellite I cross-referenced open databases: who built it, how much it weighs, which
program it belongs to, whether it's civil, commercial or military, whether it's registered with the UN, and which
radio frequencies it transmits on. For the ISS you even get the frequencies of the Russian spacesuits, which you
can pick up with a cheap SDR dongle.

**Pollution seen from space.** Nitrogen dioxide and sulfur dioxide measured by Sentinel-5P, carbon monoxide and methane,
fine particles and the ozone layer, right on the globe. Click anywhere to get the real value measured by the satellite.
The map is a 7-day average that my server computes itself from NASA's daily data.

**The cameras.** Here I only wanted real images: the latest photos taken by the ISS crew, the whole Earth captured
every 10 minutes by the GOES weather satellites, the Sun seen by the SDO and SOHO probes. Every image shows its
real capture date. There's also a gallery of the Moon and the planets that only keeps pictures where you can
really see the body well (more on that below, it was the hardest part).

<table><tr>
<td><img src="docs/screenshots/camera-iss.png" alt="Photos taken by the ISS crew"></td>
<td><img src="docs/screenshots/galerie.png" alt="Gallery of the Moon and planets"></td>
</tr></table>

**And more.** The solar system in 3D with 22 comets and asteroids (you can jump 100 years ahead to watch Halley
come back), tonight's sky from your location, eclipses with a countdown, meteor showers rated according to the
Moon, asteroids passing close to Earth, upcoming rocket launches and the latest exoplanet discoveries.

## The science part

This is the part I'm proudest of, because I had to actually understand things before coding them.

- **Where the satellites are.** Each satellite is described by two lines of numbers (a "TLE"). The SGP4 algorithm
  turns them into a position, accounting for atmospheric drag and the fact that the Earth isn't a perfect sphere.
- **When the ISS passes over me.** I wrote the frame transformations myself: from the inertial frame (TEME) to the
  Earth-fixed frame (using sidereal time), then to the local horizon. A bisection search then finds the exact second
  the ISS crosses the horizon. To know if it's visible to the naked eye, it has to be lit by the Sun while the
  observer is in the dark, hence a model of the Earth's shadow.
- **Comets.** Kepler's equation solved with Newton's method, its hyperbolic version for objects coming from other
  stars ('Oumuamua, Borisov, 3I/ATLAS), and Barker's equation for parabolic orbits.
- **Asteroid sizes.** Estimated from their absolute magnitude: D = 1329 / √albedo × 10^(−H/5).
- **Pollution.** I read the color of each pixel and convert it back into a value using NASA's official color table,
  then average 7 days pixel by pixel to fill the gaps left by clouds.
- **The gallery.** A computer can't tell if a photo is beautiful. But it can measure whether the body is alone,
  whole, sharp and on a black background: image borders, connected components, and Laplacian variance for sharpness.

All of this is checked by 64 automated tests, some of which compare my results with real events: the total solar
eclipse of August 12, 2026 in Spain, the lunar eclipse of September 7, 2025, and Halley's return in 2061.

## What didn't work

A lot of things. A few examples: CelesTrak blocked me because I was downloading too often, Halley's comet was
missing because my cache kept errors in memory for 24 hours, the 3D models came out completely black and then
completely white, and my first gallery kept a picture of a tree because it was called "Moon Tree".

I wrote everything down (the problem, the cause and the fix) in the [dev log](docs/JOURNAL.en.md). Honestly, it's
the file that best shows how I worked.

## Run it yourself

```bash
git clone https://github.com/Parzivald1/orbitra.git
cd orbitra
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn orbitra.main:app --reload
```

Then open http://127.0.0.1:8000 (API docs at `/docs`). With Docker:
`docker build -t orbitra . && docker run -p 8000:8000 orbitra`.

Two optional settings in `.env.example`: `CESIUM_ION_TOKEN` for 3D buildings, and `EOL_API_KEY` for the ISS
"trip replay" made of real crew photos (a free key you request from NASA). On a phone, the app can be installed
from the browser like a native app.

## Data sources

Everything is free and public, and I'm grateful to the people behind it: [CelesTrak](https://celestrak.org) for
orbits, [Jonathan McDowell's GCAT](https://planet4589.org/space/gcat/) and [SatNOGS](https://db.satnogs.org) for
OSINT, [Wikidata](https://www.wikidata.org) and Wikipedia, [JPL](https://ssd.jpl.nasa.gov) for comets and asteroids,
[The Space Devs](https://thespacedevs.com) for launches, the [NASA Exoplanet Archive](https://exoplanetarchive.ipac.caltech.edu),
the [Spaceflight News API](https://spaceflightnewsapi.net), the [IMO](https://www.imo.net) for meteor showers, Esri for the
globe imagery, [NASA 3D models](https://github.com/nasa/NASA-3D-Resources), NASA GIBS, NOAA (GOES), NASA (SDO, EPIC,
ISS photos) and ESA (SOHO).

## Roadmap

- [x] Orbit, solar system, night sky, events, launches, discoveries
- [x] HD Earth, 3D satellites, real cameras, gallery, OSINT file
- [x] Pollution measured from space (NO₂, SO₂, CO, methane, particles, ozone): that was the original idea
- [ ] A notification when the ISS is about to pass over you
- [ ] Android and iOS apps
- [ ] English interface

## How I built it

I built this project with the help of AI assistants (Claude Code, plus Antigravity for reviews), a bit like
pair programming. I decided what to build, tested everything, found what was wrong and checked the calculations
against real events. Every mistake and how we fixed it is in the dev log.

## License

[MIT](LICENSE): feel free to reuse the code.

<div align="center"><sub>Parzivald1 · Paris, France · <a href="https://github.com/Parzivald1">@Parzivald1</a></sub></div>
