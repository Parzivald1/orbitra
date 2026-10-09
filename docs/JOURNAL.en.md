# Dev log

[Version française](JOURNAL.md)

This is where I write down what I do, what breaks and how I fix it. At first it was just for me, so I wouldn't make
the same mistakes twice. Now I think it's also the best way to show how I work.

---

## Day 1: v0.1

### Where it started

At first I just wanted to know where the ISS was. Then I thought: why stop there? Satellites, debris, eclipses,
comets, meteor showers, launches… I split everything into six independent modules so I could finish each one before
moving on. Otherwise I knew I'd start everything and finish nothing.

### Technical choices, and why

Python with FastAPI for the server, because I know Python and FastAPI generates the API documentation on its own.
For the interface, plain JavaScript with no framework: no Node, no build step, you open it and it works. CesiumJS for
the globe (it's what professionals use for this kind of visualization) and Three.js for the solar system, since it's lighter.

The most important choice: computing the positions of 18,000 satellites **in the browser**, not on the server. The
server sends the data once, and each user's browser does the math. Otherwise, with several users, the server would
have melted.

I also wanted to write the important calculations myself (Kepler, frame transformations, passes over your location)
instead of calling a library that does everything. It takes longer, but it's the only way to really understand
it, and it can be tested.

### What worked on the first try

Seven API routes out of nine, and the first 41 tests. When I saw the catalog load with 18,621 objects, including
10,658 Starlinks and 2,680 pieces of debris, it was a shock. I knew there were a lot, but not that many.

### What broke

**CelesTrak blocked me.** After testing the URLs a few times, the site replied "GP data has not updated since your
last successful download". Their data only changes every 2 hours and they refuse repeated downloads. Fair enough,
they run on donations. I added a disk cache: a group is never requested again before 2 hours, and if CelesTrak
refuses, the last copy is kept.

**"Tonight's sky" crashed with a 500 error.** I was passing `+1` and `-1` to the rise/set function, which expects
`Direction.Rise` and `Direction.Set`. A silly mistake, but it taught me to read the docs first.

**Eclipses crashed because of a `NaN`.** During a partial eclipse, the Moon's shadow doesn't touch the Earth, so
there's no "central point" and the library returns `NaN`, which JSON rejects. Now that point is only sent when it
exists, and a test makes sure no `NaN` gets through.

**The "latest" exoplanets were from 2022.** It took me a while: NASA's archive applies `TOP 30` before `ORDER BY`.
So it took 30 random planets, then sorted them. I now fetch the last two years of discoveries and sort them myself.

**The globe was completely black in my automated screenshots.** The satellites showed up but not the Earth. I wrote
a test page: Cesium said the Earth was loaded. In a real Chrome window, everything displayed fine. The problem was
headless Chrome, not my code. Lesson learned: check your testing tool before blaming your code.

**Halley's comet was missing.** Actually 8 objects out of 22 were missing. I was sending 22 requests at once to JPL,
which rejected some of them, and my cache kept the failure for 24 hours. Two mistakes in one. Fix: at most 4 parallel
requests, 3 retries, and errors are never cached.

**Mercury was "visible" in the middle of twilight.** And Jupiter was "best seen" at 7:57 am, after sunrise. My night
window ran from sunset to sunrise, but you can't see anything until the Sun is at least 6° below the horizon. Fixed,
and a planet now has to rise at least 10° to count.

**Five launch site codes were wrong.** I had written them from memory. Bad idea. I switched to CelesTrak's official
list (42 sites). Since then I always check the source.

### Security

I do pentesting on the side, so I couldn't let this slide. Any text coming from an external API is escaped before
being displayed (otherwise a malicious article title could run code: an XSS flaw). Links can only be http or https.
The satellite number is validated before going into the query sent to Wikidata (injection protection). GPS
coordinates are validated on the server. And there are no secret keys in the code.

---

## Day 1, later: v0.2

I looked at the first version with fresh eyes: the Earth was pixelated, you couldn't see anything when zooming in,
the satellites were boring dots, and I wanted real images from space. Not simulations.

### The pixelated Earth

Two causes. Cesium's default texture is a small low-resolution image, and on a Retina screen Cesium renders at
**half the screen resolution** by default to save power. I plugged in high-resolution satellite imagery (you can see
the rooftops of Paris), forced the real resolution and added anti-aliasing.

### The real satellite in 3D

NASA publishes 3D models of its spacecraft. I found 22 that match satellites still in orbit, and checked each
satellite number in the catalog before linking them.

The models first came out **completely black**. Cesium's realistic rendering has no ambient light in space, so the
unlit side is black. I wrote a small *shader* (a program that runs on the graphics card) to light them properly.

Then the ISS came out **completely white**. I opened the file: NASA's model has no colors at all, its 19 materials are
all grey. So I identified the parts by their shape. The solar arrays, for example, are the big flat 30 × 45 m piece with
very few vertices. Then I wrote a script (`tools/recolor_glb.py`) that only changes the colors in the file, without
touching the geometry. That's the bug I enjoyed solving the most.

### Other globe bugs

- A **yellow icon stayed stuck on the ISS** in close-up view. It was the station's other modules (Nauka, etc.),
  cataloged separately. And at startup, their positions weren't computed yet when I looked for the ISS's neighbors.
  Their positions are now computed at selection time.
- **Stripes across the Earth** when following the ISS. I turned effects off one by one to find the culprit: Cesium's
  day/night lighting near the terminator. It now fades out below 6,500 km.
- **18,000 tiny satellite drawings** were painful to look at. They became soft glowing dots, and detail is kept for
  the selected satellite.
- **The camera flew off over France on its own** because of a recentering triggered at the wrong time.

### Real cameras

I set myself one rule: **no computer-generated image presented as real**. The 3D view on the globe is labeled
"reconstruction". The cameras are real images with their real date: ISS crew photos, the whole Earth every 10 minutes
(GOES), the Sun (SDO, SOHO), the Earth seen from 1.5 million km away (DSCOVR).

Small surprise: the "real-time" feed from the SDO probe was 18 days old. So the app shows the age of every image and
only says "real time" if it's less than 6 hours old.

### The gallery, the hardest part

I wanted a gallery that only keeps photos where you can really see a planet or the Moon well.

The first version filtered on title text. It kept a picture of a tree ("Apollo 14 Moon Tree", grown from seeds that
had flown around the Moon), a moonrise over a city, a hill called "Mars Hill", maps, an audio recording and
duplicates. Not great.

For the second version I made it analyze **the image itself**: the edges must be black (space background), there must
be one single large bright area (one body, not a montage), of reasonable size, roughly round, and sharp (Laplacian
variance). I calibrated it on real images before turning it on. Result: 49 real portraits out of 197 analyzed images.
Jupiter by Hubble, the Moon by Galileo, Uranus by Voyager 2.

### The ISS onboard camera

The latest crew photos are displayed, and while scrolling through them I found out that French astronaut
**Sophie Adenot** is on board right now.

I also prepared a "trip replay": astronauts often shoot bursts (one photo per second), and played back to back they
show exactly what they saw. But the database that gives the time and position of each photo needs a free NASA key,
which I requested. Until then, the photo grouping is tested with fake data. I'd rather say it clearly: this part
hasn't run on real data yet.

---

## Day 1, again: OSINT

I do pentesting, so OSINT (open-source intelligence) is my thing. For satellites, the big OSINT tools are useless:
they're built to investigate websites or people. The real sources are open databases.

- **GCAT**, by Jonathan McDowell (astrophysicist at the Harvard-Smithsonian Center for Astrophysics): the most complete
  database there is, 69,433 objects. Manufacturer, mass, dimensions, program, and most importantly the user class:
  civil, commercial, **military** or amateur. It also has each satellite's UN registration.
- **SatNOGS**, an open-source network of amateur radio stations: the frequencies of each satellite. The ISS has 50
  transmitters, including the Russian spacesuits, which you can listen to with a €30 SDR dongle.

I also wanted to use the UCS database, but it's no longer available at its old address.

One small bug caught by the tests: "Cylindre +  2 panneaux" with a double space. Details like that are exactly why I write tests.

---

## Next

Pollution seen from space (NO₂, methane, CO₂ measured by Sentinel-5P) shown on the globe. It was my original idea and
I still haven't done it, so it's about time.
