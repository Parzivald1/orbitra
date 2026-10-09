"""Éclipses, étoiles filantes et ciel : comparaison avec des événements connus."""
from datetime import date, datetime, timezone

import astronomy

from orbitra.astro import eclipses, meteors, sky
from orbitra.astro.timeutil import to_astro


def test_eclipse_totale_espagne_12_aout_2026():
    e = eclipses.solar_global(to_astro(datetime(2026, 8, 1, tzinfo=timezone.utc)), count=1)[0]
    assert e["kind"] == "totale"
    assert e["peak"].startswith("2026-08-12")


def test_eclipse_totale_de_lune_7_septembre_2025():
    e = eclipses.lunar(to_astro(datetime(2025, 9, 1, tzinfo=timezone.utc)), count=1)[0]
    assert e["kind"] == "totale"
    assert e["peak"].startswith("2025-09-07")
    assert 75 <= e["duration_total_min"] <= 90


def test_eclipse_partielle_sans_point_central():
    for e in eclipses.solar_global(to_astro(datetime(2026, 1, 1, tzinfo=timezone.utc)), count=8):
        if e["kind"] == "partielle":
            assert "latitude" not in e  # pas de NaN envoyé à l'interface


def test_quadrantides_a_cheval_sur_deux_annees():
    qua = next(s for s in meteors.showers() if s["code"] == "QUA")
    assert meteors.is_active(qua, date(2026, 12, 30))
    assert meteors.is_active(qua, date(2027, 1, 5))
    assert not meteors.is_active(qua, date(2026, 7, 1))


def test_prochain_pic_des_perseides():
    per = next(s for s in meteors.showers() if s["code"] == "PER")
    assert meteors.next_peak(per, date(2026, 10, 9)) == date(2027, 8, 12)
    assert meteors.next_peak(per, date(2026, 8, 13)) == date(2026, 8, 12)  # la nuit d'après compte encore


def test_note_selon_la_lune():
    assert meteors.rating(150, 0.0) == "excellente"
    assert meteors.rating(150, 1.0) == "bonne"
    assert meteors.rating(10, 1.0) == "faible"


def test_liste_triee_et_complete():
    items = meteors.upcoming(date(2026, 10, 9))
    assert len(items) == len(meteors.showers())
    assert [i["days_to_peak"] for i in items] == sorted(i["days_to_peak"] for i in items)


def test_ciel_du_soir_paris():
    result = sky.tonight(48.8361, 2.3364, 400, datetime(2026, 10, 9, 12, tzinfo=timezone.utc))
    assert result["sun"]["set"].startswith("2026-10-09T17")  # ~19 h heure de Paris
    assert {p["name"] for p in result["planets"]} >= {"Mars", "Jupiter", "Saturne"}
    assert 0 <= result["moon"]["illumination"] <= 1
