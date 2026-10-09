"""Caméras réelles : analyse d'image de la galerie, filtres de texte, film du trajet de l'ISS."""
from io import BytesIO

from PIL import Image, ImageDraw

from orbitra.services import gallery, imagecheck, isscam


def _png(draw) -> bytes:
    img = Image.new("RGB", (400, 400), "black")
    draw(ImageDraw.Draw(img))
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _planet(d):
    d.ellipse((100, 100, 300, 300), fill=(200, 160, 110))
    for y in range(120, 290, 18):  # bandes nuageuses : du détail pour la netteté
        d.line((110, y, 290, y), fill=(150, 100, 60), width=6)


def test_planete_seule_sur_fond_noir_acceptee():
    r = imagecheck.analyse(_png(_planet))
    assert r["ok"], r


def test_gros_plan_de_surface_refuse():
    r = imagecheck.analyse(_png(lambda d: d.rectangle((0, 0, 400, 400), fill=(170, 120, 90))))
    assert not r["checks"]["fond spatial"]


def test_montage_de_plusieurs_astres_refuse():
    def several(d):
        for x in (20, 150, 280):
            d.ellipse((x, 160, x + 90, 250), fill=(220, 220, 220))
    assert not imagecheck.analyse(_png(several))["checks"]["un seul astre"]


def test_point_minuscule_refuse():
    r = imagecheck.analyse(_png(lambda d: d.ellipse((195, 195, 203, 203), fill="white")))
    assert not r["checks"]["taille"]


def test_filtres_de_texte():
    assert gallery.passes_text("Hubble Takes Mars Portrait Near Close Approach") == "mars"
    assert gallery.passes_text("Full Moon") == "lune"
    assert gallery.passes_text("Artist's concept of Saturn") is None
    assert gallery.passes_text("Full Moon rises over the city") is None
    assert gallery.passes_text("Apollo 14 Moon Tree") is None
    assert gallery.passes_text("Triton - Neptune Largest Satellite") is None
    assert gallery.passes_text("Hubble Views Ancient Storm on Jupiter - Montage") is None


def _row(frame, second, directory="ESC/small/ISS075"):
    return {"nadir.mission": "ISS075", "nadir.frame": str(frame), "nadir.pdate": "20260920",
            "nadir.ptime": f"1200{second:02d}", "nadir.lat": 10.0, "nadir.lon": 20.0, "nadir.elev": 35,
            "images.directory": directory, "images.filename": f"ISS075-E-{frame}.JPG"}


def test_film_du_trajet_regroupe_les_photos_consecutives():
    rows = [_row(1000 + i, i) for i in range(25)]          # 25 photos, une par seconde
    rows += [_row(2000 + i, i) for i in range(5)]           # rafale trop courte : ignorée
    seqs = isscam.build_sequences(rows)
    assert len(seqs) == 1
    assert seqs[0]["count"] == 25 and seqs[0]["daylight"]
    assert seqs[0]["frames"][0]["src"].endswith("ESC/small/ISS075/ISS075-E-1000.JPG")


def test_film_coupe_si_trou_dans_le_temps():
    rows = [_row(1000 + i, i) for i in range(20)] + [_row(1020 + i, 40 + i) for i in range(5)]
    seqs = isscam.build_sequences(rows)
    assert len(seqs) == 1 and seqs[0]["count"] == 20
