"""Pollution et composition de l'atmosphère vues depuis l'espace (NASA GIBS).

Les satellites ne « voient » pas un gaz directement : ils mesurent la lumière du Soleil
réfléchie par la Terre, et chaque molécule absorbe certaines longueurs d'onde bien précises
(spectroscopie d'absorption). Plus il y a de NO₂ entre le sol et le satellite, plus ses raies
d'absorption sont marquées. C'est comme ça que Sentinel-5P cartographie la pollution de la planète
chaque jour.

GIBS fournit ces mesures sous forme de tuiles colorées. Pour retrouver le chiffre exact sous le
curseur, on lit la couleur du pixel et on la convertit avec la table de couleurs officielle
(colormap) publiée par la NASA : chaque couleur correspond à un intervalle de valeurs.
"""
import asyncio
import math
import re
from io import BytesIO

from PIL import Image

from .. import net
from ..cache import ttl_cache

CAPABILITIES = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml"
TILE = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{layer}/default/{date}/GoogleMapsCompatible_Level6/{z}/{y}/{x}.png"
ZOOM = 6  # niveau maximal de ces couches (résolution ~2,4 km par pixel à l'équateur)

# levels : repères indicatifs pour situer une valeur (seuil bas, libellé)
LAYERS = [
    {
        "key": "no2", "fade_below": 1.5e15, "hotspots": [("Chine de l'Est", 32.0, 118.5), ("Plaine du Pô (Italie)", 45.4, 9.6), ("Paris", 48.86, 2.35), ("Highveld (Afrique du Sud)", -26.3, 29.2)],
        "layer": "TROPOMI_L2_Nitrogen_Dioxide_Tropospheric_Column",
        "name": "Dioxyde d'azote", "formula": "NO₂", "satellite": "Sentinel-5P", "instrument": "TROPOMI",
        "units": "molécules/cm²",
        "what": "Gaz brun-rouge émis surtout par les moteurs, les centrales et l'industrie. Il vit peu de temps "
                "(quelques heures) : on voit donc presque directement les villes, les autoroutes et les ports.",
        "health": "Irrite les poumons et aggrave l'asthme. Il participe aussi à la formation d'ozone au sol.",
        "levels": [(0, "air propre"), (1e15, "faible"), (3e15, "modéré (zone urbaine)"), (7e15, "élevé"), (1.5e16, "très élevé")],
    },
    {
        "key": "so2", "fade_below": 0.5, "hotspots": [("Etna (Sicile)", 37.75, 15.0), ("Norilsk (Sibérie)", 69.35, 88.2), ("Kilauea (Hawaï)", 19.4, -155.3)],
        "layer": "TROPOMI_L2_Sulfur_Dioxide_Total_Vertical_Column",
        "name": "Dioxyde de soufre", "formula": "SO₂", "satellite": "Sentinel-5P", "instrument": "TROPOMI",
        "units": "DU",
        "what": "Craché par les volcans, les centrales à charbon et les fonderies. Les panaches volcaniques sont "
                "spectaculaires : ils se voient sur des milliers de kilomètres.",
        "health": "Irritant respiratoire, et il retombe en pluies acides.",
        "levels": [(-1e9, "rien de notable"), (0.5, "faible"), (1, "notable"), (3, "élevé (volcan ou industrie lourde)")],
    },
    {
        "key": "co", "fade_below": 95, "hotspots": [("Feux d'Afrique centrale", -8.0, 22.0), ("Amazonie", -9.0, -60.0), ("Sibérie", 62.0, 120.0)],
        "layer": "AIRS_L3_Carbon_Monoxide_500hPa_Volume_Mixing_Ratio_Daily_Day",
        "name": "Monoxyde de carbone", "formula": "CO", "satellite": "Aqua", "instrument": "AIRS",
        "units": "ppbv",
        "what": "Produit par toutes les combustions incomplètes, surtout les feux de forêt et de savane. Mesuré "
                "vers 5 500 m d'altitude, là où les vents l'emportent d'un continent à l'autre.",
        "health": "Toxique à forte dose. Ici c'est surtout un traceur des grands incendies.",
        "levels": [(0, "fond normal"), (100, "modéré"), (150, "élevé (incendies)"), (200, "très élevé")],
    },
    {
        "key": "ch4", "hotspots": [("Bangladesh (rizières)", 23.7, 90.4), ("Golfe Persique", 27.0, 51.0), ("Paris", 48.86, 2.35)],
        "layer": "AIRS_L3_Methane_400hPa_Volume_Mixing_Ratio_Daily_Day",
        "name": "Méthane", "formula": "CH₄", "satellite": "Aqua", "instrument": "AIRS",
        "units": "ppbv",
        "what": "Deuxième gaz à effet de serre après le CO₂ : élevage, rizières, zones humides, fuites de gaz et "
                "de pétrole. Sur 20 ans, il réchauffe environ 80 fois plus que le CO₂.",
        "health": "Pas toxique à ces niveaux, mais c'est un puissant gaz à effet de serre.",
        "levels": [(0, "plus bas que la moyenne"), (1850, "proche de la moyenne"), (1950, "élevé")],
    },
    {
        "key": "aod", "fade_below": 0.15, "hotspots": [("Plaine du Gange (Inde)", 26.5, 82.0), ("Chine de l'Est", 32.0, 118.5), ("Poussières du Sahara sur l'Atlantique", 15.0, -25.0)],
        "layer": "MODIS_Combined_Value_Added_AOD",
        "name": "Particules fines et aérosols", "formula": "AOD", "satellite": "Terra et Aqua", "instrument": "MODIS",
        "units": "sans unité",
        "what": "L'épaisseur optique des aérosols : à quel point les particules (fumées, poussières du désert, "
                "pollution, sel marin) bloquent la lumière. 0,1 = ciel très pur, plus de 1 = ciel opaque.",
        "health": "Les particules fines pénètrent profondément dans les poumons et le sang.",
        "levels": [(0, "air très pur"), (0.1, "léger voile"), (0.3, "brumeux"), (0.6, "pollué"), (1, "très chargé (fumée, poussières)")],
    },
    {
        "key": "o3", "hotspots": [("Antarctique (trou d'ozone)", -75.0, 0.0), ("Paris", 48.86, 2.35), ("Équateur", 0.0, -30.0)],
        "layer": "OMPS_Ozone_Total_Column",
        "name": "Couche d'ozone", "formula": "O₃", "satellite": "Suomi NPP", "instrument": "OMPS",
        "units": "DU",
        "what": "La quantité totale d'ozone au-dessus de nous, surtout dans la stratosphère, où il nous protège des UV. "
                "Sous 220 unités Dobson, on parle de trou dans la couche d'ozone (au-dessus de l'Antarctique au printemps austral).",
        "health": "Moins d'ozone en altitude = plus d'UV au sol (coups de soleil, cancers de la peau).",
        "levels": [(0, "trou d'ozone"), (220, "bas"), (280, "normal"), (380, "élevé")],
    },
]
BY_KEY = {l["key"]: l for l in LAYERS}


# ---------- Métadonnées GIBS (dates disponibles, légendes, tables de couleurs) ----------

@ttl_cache(6 * 3600)
async def _capabilities() -> str:
    return await net.get_text(CAPABILITIES)


def parse_layer_meta(xml: str, layer: str) -> dict:
    block = next((b for b in re.findall(r"<Layer>(.*?)</Layer>", xml, re.S)
                  if f"<ows:Identifier>{layer}</ows:Identifier>" in b), "")
    default = re.search(r"<Default>(.*?)</Default>", block)
    legend = re.search(r"xlink:href='([^']+_H\.svg)'", block)
    colormap = re.search(r"xlink:href='([^']+colormaps/v1\.3/[^']+\.xml)'", block)
    ranges = re.findall(r"<Value>([^<]+)</Value>", block)
    first = ranges[0].split("/")[0] if ranges else None
    return {
        "latest": default.group(1)[:10] if default else None,
        "first": first[:10] if first else None,
        "legend": legend.group(1) if legend else None,
        "colormap": colormap.group(1) if colormap else None,
    }


async def layers() -> list[dict]:
    xml = await _capabilities()
    out = []
    for l in LAYERS:
        meta = parse_layer_meta(xml, l["layer"])
        if not meta["latest"]:
            continue  # couche retirée par la NASA : on ne l'affiche pas
        out.append({**{k: v for k, v in l.items() if k not in ("levels", "hotspots", "fade_below")}, **meta,
                    "fades_background": l.get("fade_below") is not None,
                    "hotspots": [{"name": n, "lat": la, "lon": lo} for n, la, lo in l.get("hotspots", [])],
                    "tile_url": TILE.replace("{layer}", l["layer"]).replace("{z}", "{z}")})
    return out


# ---------- Lecture d'une valeur sous le curseur ----------

def lonlat_to_pixel(lat: float, lon: float, z: int = ZOOM) -> tuple[int, int, int, int]:
    """Coordonnées -> (tuile x, tuile y, pixel x, pixel y) en projection Web Mercator."""
    lat = max(min(lat, 85.0511), -85.0511)
    n = 2 ** z * 256
    x = (lon + 180) / 360 * n
    rad = math.radians(lat)
    y = (1 - math.log(math.tan(rad) + 1 / math.cos(rad)) / math.pi) / 2 * n
    x, y = min(int(x), n - 1), min(int(y), n - 1)
    return x // 256, y // 256, x % 256, y % 256


def _bound(text: str) -> float | None:
    text = text.strip()
    if text in ("-INF", "INF", "+INF", ""):
        return None
    return float(text)


def parse_colormap(xml: str) -> list[dict]:
    """Table des couleurs : rgb -> intervalle de valeurs [bas, haut)."""
    entries = []
    for m in re.finditer(r"<ColorMapEntry ([^>]+)/>", xml):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        rgb = tuple(int(c) for c in attrs["rgb"].split(","))
        nodata = attrs.get("nodata") == "true" or attrs.get("transparent") == "true"
        value = attrs.get("value") or attrs.get("sourceValue")
        low = high = None
        if value and value.startswith(("[", "(")):
            parts = value.strip("[]()").split(",", 1)
            # correctif : certaines tables donnent une valeur unique (« [0.99] ») et pas un intervalle
            low, high = (_bound(parts[0]), _bound(parts[1])) if len(parts) == 2 else (_bound(parts[0]),) * 2
        entries.append({"rgb": rgb, "nodata": nodata, "low": low, "high": high, "label": attrs.get("label")})
    return entries


def lookup(entries: list[dict], rgb: tuple[int, int, int]) -> dict | None:
    """Retrouve l'intervalle d'une couleur (exacte, sinon la plus proche)."""
    best, best_d = None, float("inf")
    for e in entries:
        d = sum((a - b) ** 2 for a, b in zip(e["rgb"], rgb))
        if d < best_d:
            best, best_d = e, d
    return best if best and best_d <= 75 else None  # au-delà, la couleur n'appartient pas à la table


def level_of(layer: dict, value: float) -> str:
    label = layer["levels"][0][1]
    for threshold, name in layer["levels"]:
        if value >= threshold:
            label = name
    return label


@ttl_cache(24 * 3600)
async def _colormap(url: str) -> list[dict]:
    return parse_colormap(await net.get_text(url))


_tiles: dict[str, bytes] = {}


async def _tile(url: str) -> bytes:
    if url not in _tiles:
        if len(_tiles) > 300:
            _tiles.clear()
        r = await net.client().get(url)
        r.raise_for_status()
        _tiles[url] = r.content
    return _tiles[url]


SEARCH_RADIUS_PX = 6   # ~15 km autour du point cliqué (à nos latitudes)
SEARCH_DAYS = 7        # on remonte jusqu'à une semaine en arrière


def nearest_valid(img: Image.Image, px: int, py: int, entries: list[dict]):
    """Pixel valide le plus proche du point (les nuages laissent souvent des trous)."""
    best = None
    for dy in range(-SEARCH_RADIUS_PX, SEARCH_RADIUS_PX + 1):
        for dx in range(-SEARCH_RADIUS_PX, SEARCH_RADIUS_PX + 1):
            x, y = px + dx, py + dy
            if not (0 <= x < img.width and 0 <= y < img.height):
                continue
            d2 = dx * dx + dy * dy
            if best and d2 >= best[0]:
                continue
            r, g, b, a = img.getpixel((x, y))
            if a == 0:
                continue
            e = lookup(entries, (r, g, b))
            if e and not e["nodata"]:
                best = (d2, e)
    return best


def km_per_pixel(lat: float) -> float:
    return 40075 * math.cos(math.radians(lat)) / (2 ** ZOOM * 256)


async def value_at(key: str, date: str, lat: float, lon: float) -> dict:
    """Valeur mesurée au point ; si le satellite n'a rien vu ce jour-là, on cherche autour puis les jours d'avant."""
    from datetime import date as Date, timedelta
    layer = BY_KEY[key]
    meta = parse_layer_meta(await _capabilities(), layer["layer"])
    entries = await _colormap(meta["colormap"])
    tx, ty, px, py = lonlat_to_pixel(lat, lon)
    base = {"key": key, "requested_date": date, "lat": lat, "lon": lon, "units": layer["units"]}
    day = Date.fromisoformat(date)
    for back in range(SEARCH_DAYS):
        d = (day - timedelta(days=back)).isoformat()
        try:
            png = await _tile(TILE.format(layer=layer["layer"], date=d, z=ZOOM, x=tx, y=ty))
        except Exception:
            continue
        found = nearest_valid(Image.open(BytesIO(png)).convert("RGBA"), px, py, entries)
        if not found:
            continue
        d2, entry = found
        low, high = entry["low"], entry["high"]
        ref = low if high is None else high if low is None else (low + high) / 2
        return {**base, "found": True, "date": d, "days_before": back,
                "distance_km": round(math.sqrt(d2) * km_per_pixel(lat), 1),
                "low": low, "high": high, "value": ref,
                "level": level_of(layer, ref) if ref is not None else None}
    return {**base, "found": False,
            "reason": f"Aucune mesure dans un rayon de ~15 km sur les {SEARCH_DAYS} derniers jours "
                      "(nuages persistants, nuit polaire ou zone hors couverture)."}


# ---------- Moyenne sur plusieurs jours (comme dans les publications scientifiques) ----------
#
# Une seule journée de mesures est mouchetée : les nuages bouchent la vue et chaque pixel est bruité.
# On décode donc chaque tuile en VALEURS (grâce à la table de couleurs), on fait la moyenne pixel
# par pixel sur N jours en ignorant les trous, puis on recolore avec la même table.

def _entry_value(e: dict) -> float | None:
    low, high = e["low"], e["high"]
    if low is None and high is None:
        return None
    if low is None:
        return high
    if high is None:
        return low
    return (low + high) / 2


class Palette:
    """Conversion rapide couleur <-> valeur pour une table de couleurs GIBS."""

    def __init__(self, entries: list[dict]):
        self.data = [e for e in entries if not e["nodata"] and _entry_value(e) is not None]
        self.by_rgb = {e["rgb"]: _entry_value(e) for e in self.data}
        self.sorted = sorted(self.data, key=lambda e: _entry_value(e))
        self.values = [_entry_value(e) for e in self.sorted]

    def value(self, rgb) -> float | None:
        v = self.by_rgb.get(rgb)
        if v is None:
            e = lookup(self.data, rgb)
            v = _entry_value(e) if e else None
            self.by_rgb[rgb] = v  # mémorisé pour les pixels suivants
        return v

    def color(self, value: float) -> tuple[int, int, int]:
        import bisect
        i = min(bisect.bisect_left(self.values, value), len(self.sorted) - 1)
        if i > 0 and abs(self.values[i - 1] - value) < abs(self.values[i] - value):
            i -= 1
        return self.sorted[i]["rgb"]


_palettes: dict[str, Palette] = {}
_composites: dict[str, bytes] = {}


async def composite_tile(key: str, date: str, z: int, y: int, x: int, days: int) -> bytes:
    from datetime import date as Date, timedelta
    cache_key = f"{key}/{date}/{z}/{y}/{x}/{days}"
    if cache_key in _composites:
        return _composites[cache_key]
    layer = BY_KEY[key]
    if key not in _palettes:
        meta = parse_layer_meta(await _capabilities(), layer["layer"])
        _palettes[key] = Palette(await _colormap(meta["colormap"]))
    palette = _palettes[key]
    day = Date.fromisoformat(date)
    urls = [TILE.format(layer=layer["layer"], date=(day - timedelta(days=k)).isoformat(), z=z, x=x, y=y)
            for k in range(days)]

    async def quiet(url):
        try:
            return await _tile(url)
        except Exception:
            return None

    pngs = [p for p in await asyncio.gather(*(quiet(u) for u in urls)) if p]
    from starlette.concurrency import run_in_threadpool
    out = await run_in_threadpool(_average, pngs, palette, layer.get("fade_below"))
    if len(_composites) > 500:
        _composites.clear()
    _composites[cache_key] = out
    return out


def _alpha(value: float, fade_below: float | None) -> int:
    """Transparence progressive : invisible au niveau de fond, opaque au double."""
    if fade_below is None or value >= 2 * fade_below:
        return 255
    if value <= fade_below:
        return 0
    return int(255 * (value - fade_below) / fade_below)


def _average(pngs: list[bytes], palette: Palette, fade_below: float | None = None) -> bytes:
    size = 256 * 256
    total, count = [0.0] * size, [0] * size
    for png in pngs:
        img = Image.open(BytesIO(png)).convert("RGBA")
        for i, (r, g, b, a) in enumerate(img.getdata()):
            if a:
                v = palette.value((r, g, b))
                if v is not None:
                    total[i] += v
                    count[i] += 1
    pixels = []
    for i in range(size):
        if not count[i]:
            pixels.append((0, 0, 0, 0))
            continue
        v = total[i] / count[i]
        pixels.append((*palette.color(v), _alpha(v, fade_below)))
    out = Image.new("RGBA", (256, 256))
    out.putdata(pixels)
    buf = BytesIO()
    out.save(buf, "PNG", optimize=True)
    return buf.getvalue()
