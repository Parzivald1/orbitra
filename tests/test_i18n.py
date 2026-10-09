"""Traduction : tout texte français produit par le serveur doit avoir sa version anglaise."""
import json
import re

from orbitra.astro import eclipses, meteors, sky
from orbitra.config import ROOT
from orbitra.services import atmosphere, discoveries, gallery, osint, satinfo, smallbodies, spacecams

EN = json.loads((ROOT / "web" / "i18n" / "en.json").read_text(encoding="utf-8"))
PATTERNS = [re.compile(p) for p, _ in EN["patterns"]]
# textes identiques dans toutes les langues : désignations de comètes, sigles, noms propres
NEUTRAL = re.compile(r"^(\(?\d|[A-Z0-9 /.-]+$|C/|\d+P/|[A-Z][a-z]+(-[A-Z][a-z]+)?$)")


def backend_strings() -> set[str]:
    s = set()
    for _, fam in satinfo.FAMILIES:
        s |= set(fam.values())
    for d in (satinfo.DEBRIS_TEXT, satinfo.ROCKET_BODY_TEXT, satinfo.STATUS, satinfo.OBJECT_TYPES, satinfo.OWNERS,
              satinfo.LAUNCH_SITES, osint.USER_CLASS, osint.CATEGORIES, discoveries.METHODS_FR, eclipses.KINDS,
              sky.CONSTELLATIONS_FR):
        s |= set(d.values())
    s |= {n for _, n in sky.PHASES} | set(sky.QUARTERS) | {n for _, n in sky.PLANETS}
    s |= {n["note"] for n in smallbodies.NOTABLE}
    s |= {v[0] for v in gallery.TARGETS.values()}
    for c in spacecams.CAMERAS + [spacecams.LIVE_VIDEO]:
        s |= {c["title"], c["where"], c["what"]}
    for l in atmosphere.LAYERS:
        s |= {l["name"], l["what"], l["health"], l["units"]} | {n for _, n in l["levels"]} | {h[0] for h in l["hotspots"]}
    for m in meteors.showers():
        s |= {m["name"], m["radiant"], m["parent"]}
    return {x for x in s if isinstance(x, str) and x.strip()}


def translated(text: str) -> bool:
    return text in EN["exact"] or any(p.search(text) for p in PATTERNS) or bool(NEUTRAL.match(text))


def test_tous_les_textes_du_serveur_sont_traduits():
    missing = sorted(t for t in backend_strings() if not translated(t))
    assert not missing, f"{len(missing)} textes sans traduction anglaise : {missing[:15]}"


def test_motifs_valides():
    for pattern, replacement in EN["patterns"]:
        re.compile(pattern)
        assert isinstance(replacement, str)
