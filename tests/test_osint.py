"""Dossier OSINT : lecture du catalogue GCAT (données factices, sans réseau)."""
from orbitra.services import osint

INDEX = {
    "sats": {"25544": (
        {"JCAT": "S25544", "Name": "Zarya", "Manufacturer": "KHRR", "Owner": "JSC", "Bus": "77KS",
         "Mass": "20281", "DryMass": "19000", "Length": "12.6", "Diameter": "4.2", "Span": "23.9",
         "Shape": "Cyl + 2 Pan", "OpOrbit": "LLEO/I"},
        {"Class": "C", "Category": "SS", "Program": "TsM", "UNState": "US", "UNReg": "ST/SG/SER.E/614"},
    ), "99999": (
        {"JCAT": "S99999", "Name": "Secret", "Manufacturer": "-", "Owner": "-", "Bus": "-", "Mass": "-",
         "DryMass": "-", "Length": "-", "Diameter": "-", "Span": "-", "Shape": "-", "OpOrbit": "-"},
        {"Class": "D", "Category": "SIG", "Program": "-", "UNState": "-", "UNReg": "-"},
    )},
    "orgs": {"KHRR": {"Name": "GKNPTs im. M.V. Khrunichev", "Location": "Moskva:Fili"},
             "JSC": {"Name": "NASA Johnson Space Flight Center", "Location": "Houston, Texas"}},
}


def test_dossier_iss():
    d = osint.describe("25544", INDEX)
    assert d["manufacturer"] == "GKNPTs im. M.V. Khrunichev (Moskva)"
    assert d["mass_kg"] == 20281 and d["dimensions_m"]["span"] == 23.9
    assert d["category"] == "Station spatiale" and d["user"] == ["Civil (gouvernemental)"]
    assert d["un_registered"] and "ST/SG/SER.E/614" in d["un_registration"]
    assert d["shape"] == "Cylindre + 2 panneaux"


def test_satellite_militaire_peu_documente():
    d = osint.describe("99999", INDEX)
    assert d["military"] and d["category"].startswith("Renseignement")
    assert d["mass_kg"] is None and not d["un_registered"]


def test_objet_inconnu():
    assert osint.describe("12345", INDEX) is None
