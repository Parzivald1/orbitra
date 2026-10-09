"""Analyse d'image : « voit-on vraiment la planète (ou la Lune) en entier et nettement ? »

Critères mesurables sur l'image réduite à 160 px :
  1. Fond spatial : les bords de l'image sont presque entièrement noirs
     (élimine les gros plans de surface, les photos prises au sol, les schémas sur fond blanc)
  2. Un seul astre : la plus grande zone claire représente au moins 80 % de tout ce qui est clair
     (élimine les montages de plusieurs lunes, les champs d'étoiles)
  3. Taille : l'astre occupe entre 4 % et 80 % de l'image (ni un point, ni un gros plan)
  4. Forme : sa boîte englobante est à peu près carrée (disque ou croissant, pas une bande)
  5. Netteté : assez de détails (variance du laplacien), pour écarter les images floues
"""
from io import BytesIO

from PIL import Image, ImageFilter

SIZE = 160
DARK = 35            # niveau de gris (0-255) sous lequel un pixel est considéré comme du « vide spatial »
MIN_DARK_BORDER = 0.80
MIN_MAIN_BLOB = 0.80
MIN_FILL, MAX_FILL = 0.04, 0.80
MIN_SHARPNESS = 40.0


def _largest_component(mask: list[list[bool]]) -> tuple[int, tuple[int, int, int, int]]:
    """Plus grande zone de pixels clairs connectés (parcours en largeur)."""
    h, w = len(mask), len(mask[0])
    seen = [[False] * w for _ in range(h)]
    best, best_box = 0, (0, 0, 0, 0)
    for y0 in range(h):
        for x0 in range(w):
            if not mask[y0][x0] or seen[y0][x0]:
                continue
            stack, count = [(y0, x0)], 0
            seen[y0][x0] = True
            x_min = x_max = x0
            y_min = y_max = y0
            while stack:
                y, x = stack.pop()
                count += 1
                x_min, x_max, y_min, y_max = min(x_min, x), max(x_max, x), min(y_min, y), max(y_max, y)
                for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((ny, nx))
            if count > best:
                best, best_box = count, (x_min, y_min, x_max, y_max)
    return best, best_box


def analyse(data: bytes) -> dict:
    img = Image.open(BytesIO(data)).convert("L")
    img.thumbnail((SIZE, SIZE))
    w, h = img.size
    px = list(img.getdata())
    rows = [px[i * w:(i + 1) * w] for i in range(h)]

    border = rows[0] + rows[-1] + [r[0] for r in rows] + [r[-1] for r in rows]
    dark_border = sum(v < DARK for v in border) / len(border)

    mask = [[v >= DARK for v in r] for r in rows]
    bright = sum(sum(r) for r in mask)
    main, (x0, y0, x1, y1) = _largest_component(mask) if bright else (0, (0, 0, 0, 0))
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    aspect = bw / bh if bh else 0

    lap = list(img.filter(ImageFilter.FIND_EDGES).getdata())
    mean = sum(lap) / len(lap)
    sharpness = sum((v - mean) ** 2 for v in lap) / len(lap)

    metrics = {
        "dark_border": round(dark_border, 2),
        "main_blob": round(main / bright, 2) if bright else 0,
        "fill": round(bright / (w * h), 3),
        "aspect": round(aspect, 2),
        "sharpness": round(sharpness, 1),
    }
    checks = {
        "fond spatial": dark_border >= MIN_DARK_BORDER,
        "un seul astre": metrics["main_blob"] >= MIN_MAIN_BLOB,
        "taille": MIN_FILL <= metrics["fill"] <= MAX_FILL,
        "forme": 0.5 <= aspect <= 2.0,
        "netteté": sharpness >= MIN_SHARPNESS,
    }
    return {"ok": all(checks.values()), "checks": checks, "metrics": metrics}
