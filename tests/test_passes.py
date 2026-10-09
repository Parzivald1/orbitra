"""Vérifie la chaîne TLE -> position -> azimut/élévation."""
import math
from datetime import datetime, timezone

import pytest

from orbitra.astro import passes

# TLE de l'ISS (archive, époque 2024-01-01) : les tests ne dépendent pas d'Internet
ISS_L1 = "1 25544U 98067A   24001.50000000  .00016717  00000-0  30235-3 0  9990"
ISS_L2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.49815325432598"


def test_gmst_a_j2000():
    # valeur de référence : 280,46061837° à J2000.0
    assert math.degrees(passes.gmst(2451545.0)) == pytest.approx(280.46061837, abs=1e-6)


def test_observateur_equateur_greenwich():
    assert passes.geodetic_to_ecef(0, 0, 0) == pytest.approx((6378.137, 0, 0), abs=1e-6)


def test_satellite_au_zenith():
    obs = passes.geodetic_to_ecef(45, 3, 0)
    up = [c * 1.1 for c in obs]  # 10 % plus loin dans la même direction ≈ à la verticale
    _, el, _ = passes.look_angles(up, obs, 45, 3)
    assert el > 89.5


def test_points_cardinaux():
    assert passes.compass(0) == "N"
    assert passes.compass(90) == "E"
    assert passes.compass(225) == "SO"


def test_passages_iss_coherents():
    start = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
    found = passes.find_passes(ISS_L1, ISS_L2, 48.8361, 2.3364, 400, start, hours=48)
    assert found, "l'ISS survole forcément la France en 48 h"
    for p in found:
        assert 10 <= p["max_elevation"] <= 90
        assert 60 < p["duration_s"] < 15 * 60  # un passage d'ISS dure quelques minutes
        assert p["rise"] < p["max"] < p["set"]


def test_ombre_de_la_terre():
    now = datetime(2024, 6, 21, 12, tzinfo=timezone.utc)
    # point situé derrière la Terre par rapport au Soleil (côté nuit), en orbite basse
    import astronomy
    from orbitra.astro.timeutil import to_astro
    s = astronomy.GeoVector(astronomy.Body.Sun, to_astro(now), True)
    n = math.sqrt(s.x**2 + s.y**2 + s.z**2)
    night_side = (-s.x / n * 6800, -s.y / n * 6800, -s.z / n * 6800)
    day_side = tuple(-c for c in night_side)
    assert passes.is_sunlit(day_side, now)
    assert not passes.is_sunlit(night_side, now)
