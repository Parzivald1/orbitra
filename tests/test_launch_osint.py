"""Dossier de lancement : lecture de Launch Library, météo, désignation retrouvée par l'heure."""
import asyncio

from orbitra.services import launch_osint as lo

RAW = {
    "id": "x", "name": "Falcon 9 | Crew-14", "net": "2026-10-20T12:00:00Z",
    "status": {"abbrev": "Go", "name": "Go for Launch", "description": "..."},
    "launch_service_provider": {"name": "SpaceX", "total_launch_count": 200, "successful_launches": 198},
    "rocket": {"configuration": {"full_name": "Falcon 9 Block 5", "length": 70, "leo_capacity": 22800},
               "launcher_stage": [{"launcher": {"serial_number": "B1090", "flights": 5, "flight_proven": True},
                                   "launcher_flight_number": 6, "landing": {"attempt": True, "success": None,
                                   "type": {"name": "Autonomous Spaceport Drone Ship"}, "location": {"name": "ASOG"}}}],
               "spacecraft_stage": {"destination": "International Space Station",
                                    "launch_crew": [{"astronaut": {"name": "Kayla Barron", "nationality": "American"},
                                                     "role": {"role": "Commander"}}]}},
    "mission": {"name": "Crew-14", "orbit": {"name": "Low Earth Orbit", "abbrev": "LEO"}, "agencies": [{"name": "NASA"}]},
    "pad": {"name": "LC-39A", "latitude": "28.608", "longitude": "-80.604", "location": {"name": "KSC", "timezone_name": "America/New_York"}},
    "pad_turnaround": "P3DT4H10M",
}


def test_lecture_du_lancement():
    l = lo.simplify(RAW)
    assert l["status"] == "Feu vert pour le lancement"
    assert l["provider"]["stats"]["success_rate"] == 99.0
    assert l["boosters"][0]["serial"] == "B1090" and l["boosters"][0]["flight_number"] == 6
    assert l["crew"][0]["name"] == "Kayla Barron" and l["destination"] == "International Space Station"
    assert l["mission"]["orbit_fr"] == "Orbite basse" and l["pad"]["lat"] == 28.608
    assert l["counts"]["pad_turnaround"] == "3 j 4 h"


def test_meteo_de_tir():
    assert lo.weather_verdict(15, 25, 20, 0, 100)["level"] == "favorable"
    assert lo.weather_verdict(15, 25, 20, 0, 2000)["level"] == "défavorable"  # orage = foudre
    assert lo.weather_verdict(45, 50, 20, 0, 0)["level"] == "à surveiller"


def test_designation_retrouvee_par_l_heure(monkeypatch):
    async def fake():
        return [(2461315.6625, "2026-228"), (2461320.6423, "2026-229")]
    monkeypatch.setattr(lo, "_gcat_recent_launches", fake)
    assert asyncio.run(lo.designator_for("2026-10-02T03:54:00Z")) == "2026-228"
    assert asyncio.run(lo.designator_for("2026-10-04T12:00:00Z")) is None  # aucun tir à moins de 30 min
