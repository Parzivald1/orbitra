"""Vérifie la mécanique orbitale sur des cas dont on connaît la réponse."""
import math

import pytest

from orbitra.astro import kepler

# Orbite quasi circulaire de 1 UA dans le plan de l'écliptique
CIRCLE = {"e": 1e-9, "q": 1.0, "i": 0.0, "om": 0.0, "w": 0.0, "tp": 2451545.0}
YEAR = 2 * math.pi / kepler.K_GAUSS  # période d'une orbite de 1 UA (~365,25 j)


def test_annee_terrestre():
    assert YEAR == pytest.approx(365.2568983, abs=1e-4)


def test_cercle_quart_de_tour():
    x, y, z = kepler.position(CIRCLE, CIRCLE["tp"] + YEAR / 4)
    assert (x, y, z) == pytest.approx((0.0, 1.0, 0.0), abs=1e-6)


@pytest.mark.parametrize("e", [0.0167, 0.5, 0.967, 0.999])
def test_equation_kepler_elliptique(e):
    for M in (-3.0, -0.5, 0.1, 1.0, 2.9):
        E = kepler.solve_kepler_elliptic(M, e)
        assert E - e * math.sin(E) == pytest.approx(M, abs=1e-10)


@pytest.mark.parametrize("e", [1.2, 3.36, 6.14])
def test_equation_kepler_hyperbolique(e):
    for M in (-50.0, -1.0, 0.01, 2.0, 100.0):
        H = kepler.solve_kepler_hyperbolic(M, e)
        assert e * math.sinh(H) - H == pytest.approx(M, rel=1e-10, abs=1e-10)


@pytest.mark.parametrize("e", [0.2, 0.967, 1.0, 1.2, 6.14])
def test_distance_au_perihelie(e):
    """Au moment du périhélie, la distance au Soleil vaut exactement q, quel que soit e."""
    el = {"e": e, "q": 0.586, "i": 162.3, "om": 58.4, "w": 111.3, "tp": 2446470.5}
    assert math.hypot(*kepler.position(el, el["tp"])) == pytest.approx(0.586, abs=1e-9)


def test_parabole_equation_de_barker():
    el = {"e": 1.0, "q": 0.5, "i": 0, "om": 0, "w": 0, "tp": 0.0}
    x, y, _ = kepler.position(el, 40.0)
    nu, r = math.atan2(y, x), math.hypot(x, y)
    s = math.tan(nu / 2)
    assert s + s**3 / 3 == pytest.approx(kepler.K_GAUSS * 40 / math.sqrt(2 * 0.5**3), rel=1e-9)
    assert r == pytest.approx(0.5 * (1 + s * s), rel=1e-9)


def test_halley_periode_et_retour_2061():
    halley = {"e": 0.96714, "q": 0.58598, "i": 162.26, "om": 58.42, "w": 111.33, "tp": 2446470.5}  # 9 févr. 1986
    assert kepler.period_days(halley) / 365.25 == pytest.approx(75.3, abs=1.0)
    nxt = kepler.next_perihelion(halley, 2461322.5)  # octobre 2026
    year = 2000 + (nxt - 2451545.0) / 365.25
    assert 2060.5 < year < 2062.5


def test_orbite_ouverte_sans_periode():
    assert kepler.period_days({"e": 6.14, "q": 1.36}) is None


def test_trajectoire_coupee_pour_les_orbites_geantes():
    hyper = {"e": 3.36, "q": 2.0, "i": 44, "om": 308, "w": 209, "tp": 2458826.0}
    pts = kepler.orbit_path(hyper, r_max=30)
    assert max(math.hypot(*p) for p in pts) == pytest.approx(30, rel=1e-6)
