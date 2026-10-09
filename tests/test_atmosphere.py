"""Pollution vue de l'espace : géométrie des tuiles, tables de couleurs, moyenne sur plusieurs jours."""
from io import BytesIO

from PIL import Image

from orbitra.services import atmosphere as atm

COLORMAP = """<ColorMaps>
  <ColorMap title="No Data"><Entries>
    <ColorMapEntry rgb="255,0,255" transparent="true" nodata="true" ref="0"/>
  </Entries></ColorMap>
  <ColorMap title="Nitrogen Dioxide" units="molecules/cm²"><Entries>
    <ColorMapEntry rgb="255,252,199" transparent="false" value="[-INF,0.00e+00)" ref="1"/>
    <ColorMapEntry rgb="250,200,100" transparent="false" value="[1.00e+15,2.00e+15)" ref="2"/>
    <ColorMapEntry rgb="200,40,20" transparent="false" value="[1.00e+16,+INF)" ref="3"/>
    <ColorMapEntry rgb="10,10,10" transparent="false" value="[0.99]" ref="4"/>
  </Entries></ColorMap>
</ColorMaps>"""


def test_pixel_au_centre_du_monde():
    # (0°, 0°) tombe pile au coin des 4 tuiles centrales au niveau 6 (64 x 64 tuiles)
    assert atm.lonlat_to_pixel(0, 0) == (32, 32, 0, 0)


def test_pixel_aux_bords():
    tx, ty, _, _ = atm.lonlat_to_pixel(85, -180)
    assert (tx, ty) == (0, 0)
    tx, ty, px, py = atm.lonlat_to_pixel(-85, 179.999)
    assert tx == 63 and ty == 63 and px == 255


def test_lecture_de_la_table_de_couleurs():
    entries = atm.parse_colormap(COLORMAP)
    assert entries[0]["nodata"]
    assert entries[1]["low"] is None and entries[1]["high"] == 0
    assert entries[3]["low"] == 1e16 and entries[3]["high"] is None
    assert entries[4]["low"] == entries[4]["high"] == 0.99  # valeur unique (correctif)


def test_couleur_la_plus_proche():
    entries = atm.parse_colormap(COLORMAP)
    assert atm.lookup(entries, (249, 201, 101))["low"] == 1e15
    assert atm.lookup(entries, (0, 255, 0)) is None  # couleur étrangère à la table


def test_niveau_de_pollution():
    no2 = atm.BY_KEY["no2"]
    assert atm.level_of(no2, 2e14) == "air propre"
    assert atm.level_of(no2, 1.6e16) == "très élevé"


def test_transparence_du_niveau_de_fond():
    assert atm._alpha(1e15, 1.5e15) == 0
    assert atm._alpha(3e15, 1.5e15) == 255
    assert 0 < atm._alpha(2.2e15, 1.5e15) < 255
    assert atm._alpha(5, None) == 255


def _tile(color):
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    if color:
        for x in range(128):  # moitié gauche mesurée, moitié droite = trou (nuages)
            for y in range(256):
                img.putpixel((x, y), (*color, 255))
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_moyenne_sur_plusieurs_jours():
    palette = atm.Palette(atm.parse_colormap(COLORMAP))
    out = Image.open(BytesIO(atm._average([_tile((250, 200, 100)), _tile((200, 40, 20)), _tile(None)], palette)))
    r, g, b, a = out.getpixel((10, 10))
    # moyenne de 1,5e15 et 1e16 = 5,75e15 -> recolorée avec l'entrée la plus proche
    assert a == 255 and (r, g, b) in {(250, 200, 100), (200, 40, 20)}
    assert out.getpixel((200, 10))[3] == 0  # aucun jour n'a mesuré ici : reste transparent
