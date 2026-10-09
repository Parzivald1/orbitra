"""Services et API, sans appel réseau."""
import pytest
from fastapi.testclient import TestClient

from orbitra.main import app
from orbitra.services import satellites, smallbodies

TLE = """ISS (ZARYA)
1 25544U 98067A   24001.50000000  .00016717  00000-0  30235-3 0  9990
2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.49815325432598
STARLINK-1007
1 44713U 19074A   24001.50000000  .00001000  00000-0  80000-4 0  9991
2 44713  53.0540 100.0000 0001400  90.0000 270.0000 15.06400000230000
"""


def test_lecture_tle():
    sats = satellites.parse_tle(TLE)
    assert [s["id"] for s in sats] == ["25544", "44713"]
    assert sats[0]["name"] == "ISS (ZARYA)"


def test_lecture_tle_robuste_aux_lignes_parasites():
    assert len(satellites.parse_tle("ligne parasite\n" + TLE)) == 2


def test_classement():
    assert satellites.classify("ISS (ZARYA)", "station") == "station"
    assert satellites.classify("STARLINK-1007", None) == "starlink"
    assert satellites.classify("NOAA 19", "meteo") == "meteo"
    assert satellites.classify("OBJET X", None) == "autre"


def test_diametre_depuis_magnitude():
    # H = 22 et albédo 0,14 : environ 140 m (seuil des astéroïdes « potentiellement dangereux »)
    assert smallbodies.diameter_from_h(22) * 1000 == pytest.approx(141, abs=5)


def test_lecture_sbdb():
    data = {
        "object": {"fullname": "1P/Halley", "orbit_class": {"name": "Halley-type Comet"}},
        "orbit": {"epoch": "2439875.5", "elements": [
            {"name": n, "value": v} for n, v in
            [("e", "0.967"), ("q", "0.586"), ("i", "162.2"), ("om", "59.1"), ("w", "112.2"), ("tp", "2446469.97")]
        ]},
    }
    parsed = smallbodies.parse_sbdb(data)
    assert parsed["elements"]["q"] == 0.586
    assert smallbodies.parse_sbdb({"code": "300"}) is None  # recherche ambiguë


client = TestClient(app)


def test_api_sante():
    assert client.get("/api/health").json()["status"] == "ok"


def test_api_etoiles_filantes():
    r = client.get("/api/meteors")
    assert r.status_code == 200 and len(r.json()) >= 10


def test_api_valide_les_coordonnees():
    assert client.get("/api/sky", params={"lat": 123}).status_code == 422


def test_interface_servie():
    r = client.get("/")
    assert r.status_code == 200 and "ORBITRA" in r.text
