"""Recolore un modèle glTF binaire (.glb) sans toucher à sa géométrie.

Le modèle officiel de l'ISS publié par la NASA n'a aucune couleur (toutes ses pièces
sont grises à 40 %). Ce script réécrit seulement le bloc JSON du fichier pour donner
à chaque matériau une couleur réaliste. Le bloc binaire (géométrie compressée Draco)
est recopié tel quel.

Usage : python tools/recolor_glb.py entree.glb sortie.glb
"""
import json
import struct
import sys

# matériau -> couleur RVB (0-1), identifiés d'après la forme de chaque pièce
ISS_COLORS = {
    "lambert7SG.001": (0.62, 0.42, 0.16),       # panneaux solaires : grands, plats, peu de sommets -> cuivre doré
    "anisotropic1SG.001": (0.86, 0.86, 0.84),   # modules pressurisés : blanc cassé
    "apollohorns_blin.001": (0.80, 0.80, 0.78),
    "lambert3SG.001": (0.78, 0.78, 0.76),
    "blinn1SG.001": (0.55, 0.56, 0.58),         # poutre principale : métal
    "blinn3SG.001": (0.50, 0.51, 0.53),
    "bendedtruss_bli1.001": (0.52, 0.53, 0.55),
    "bendedtruss_blin.001": (0.52, 0.53, 0.55),
    "initialShadingGr.001": (0.92, 0.92, 0.92), # radiateurs : blancs
    "soyuz_blinn4SG.001": (0.42, 0.47, 0.36),   # vaisseaux Soyouz : vert-gris
    "soyuz_blinn3SG.001": (0.20, 0.25, 0.45),   # panneaux des Soyouz : bleu nuit
    "lambert4SG.001": (0.70, 0.70, 0.68),
    "lambert6SG.001": (0.66, 0.66, 0.64),
}


def recolor(src: str, dst: str, colors: dict) -> int:
    data = open(src, "rb").read()
    magic, version, _ = struct.unpack("<4sII", data[:12])
    assert magic == b"glTF" and version == 2, "pas un fichier glTF 2.0 binaire"
    json_len, json_type = struct.unpack("<II", data[12:20])
    assert json_type == 0x4E4F534A  # "JSON"
    gltf = json.loads(data[20:20 + json_len])
    rest = data[20 + json_len:]  # bloc binaire, recopié sans modification

    changed = 0
    for mat in gltf.get("materials", []):
        if mat.get("name") in colors:
            r, g, b = colors[mat["name"]]
            mat.setdefault("pbrMetallicRoughness", {})["baseColorFactor"] = [r, g, b, 1.0]
            changed += 1

    blob = json.dumps(gltf, separators=(",", ":")).encode()
    blob += b" " * (-len(blob) % 4)  # le format exige un alignement sur 4 octets
    total = 12 + 8 + len(blob) + len(rest)
    out = struct.pack("<4sII", b"glTF", 2, total) + struct.pack("<II", len(blob), 0x4E4F534A) + blob + rest
    open(dst, "wb").write(out)
    return changed


if __name__ == "__main__":
    print(f"{recolor(sys.argv[1], sys.argv[2], ISS_COLORS)} matériaux recolorés")
