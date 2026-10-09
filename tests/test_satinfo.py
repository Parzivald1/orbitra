"""Fiche satellite : textes de familles, taille, protection de la requête Wikidata."""
import asyncio

from orbitra.services import satinfo


def test_famille_par_le_nom():
    assert "Internet" in satinfo.family("STARLINK-31337", "PAY")["mission"]
    assert "TROPOMI" in satinfo.family("SENTINEL-5P", "PAY")["collects"]
    assert satinfo.family("NAVSTAR 81 (USA 319)", "PAY")["mission"].startswith("Système GPS")


def test_debris_et_etages_de_fusee():
    assert satinfo.family("FENGYUN 1C DEB", "DEB") is satinfo.DEBRIS_TEXT
    assert satinfo.family("CZ-2C R/B", "R/B") is satinfo.ROCKET_BODY_TEXT


def test_objet_inconnu_sans_famille():
    assert satinfo.family("OBJET MYSTERE", "PAY") is None


def test_taille_depuis_surface_radar():
    assert satinfo.size_from_rcs(None) is None
    assert satinfo.size_from_rcs(0.05).startswith("Petit")
    assert satinfo.size_from_rcs(399).startswith("Très grand")  # l'ISS


def test_codes_officiels_des_sites():
    assert satinfo.LAUNCH_SITES["PLMSC"] == "Plessetsk (Russie)"
    assert satinfo.LAUNCH_SITES["FRGUI"].startswith("Kourou")


def test_wikidata_refuse_un_identifiant_pirate():
    # Le numéro NORAD est injecté dans une requête SPARQL : on n'accepte que des chiffres.
    assert asyncio.run(satinfo.wikidata('1" } ; DROP')) is None
