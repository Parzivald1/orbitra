// Médias des satellites : modèles 3D officiels de la NASA et « caméras ».
//
// Modèles : dépôt public github.com/nasa/NASA-3D-Resources (domaine public), chargés directement
// depuis GitHub pour ne pas alourdir le dépôt. Clé = numéro NORAD.
//
// Caméras : seule l'ISS diffuse une vidéo en direct. Les satellites d'observation, eux, publient
// chaque jour les images de leur caméra, que la NASA met à disposition via GIBS (Global Imagery
// Browse Services) : on les affiche directement sur le globe.

const NASA_3D = "https://raw.githubusercontent.com/nasa/NASA-3D-Resources/master/3D%20Models/";
const model = (folder, file = folder) => `${NASA_3D}${encodeURIComponent(folder)}/${encodeURIComponent(file)}.glb`;

export const MODELS = {
  "25544": "models/iss.glb", // modèle NASA recoloré (l'original est entièrement gris) : voir tools/recolor_glb.py
  "20580": model("Hubble Space Telescope (A)"),
  "25994": model("Terra"),
  "27424": model("Aqua (A)"),
  "28376": model("Aura (B)"),
  "37849": model("Suomi National Polar-orbiting Partnership (Suomi NPP)"),
  "39084": model("Landsat 8"),
  "49260": model("Landsat 8"), // Landsat 9 : plateforme quasi identique à Landsat 8
  "43613": model("Ice, Clouds, and Land Elevation Satellite-2 (ICESat-2) (A)"),
  "40059": model("Orbiting Carbon Observatory (OCO) 2"),
  "28485": model("Swift"),
  "33053": model("Fermi Gamma-ray Large Area Space Telescope"),
  "43435": model("Transiting Exoplanet Survey Satellite (TESS) (B)"),
  "25867": model("Chandra X-ray Observatory"),
  "46984": model("Jason Continuity of Service (Sentinel-6)"),
  "41866": model("Geostationary Operational Environmental Satellites"), // GOES-16
  "43226": model("Geostationary Operational Environmental Satellites"), // GOES-17
  "51850": model("Geostationary Operational Environmental Satellites"), // GOES-18
  "60133": model("Geostationary Operational Environmental Satellites"), // GOES-19
  "39070": model("Tracking and Data Relay Satellites (TDRS) (B)"),      // TDRS-11
  "39504": model("Tracking and Data Relay Satellites (TDRS) (B)"),      // TDRS-12
  "42915": model("Tracking and Data Relay Satellites (TDRS) (B)"),      // TDRS-13
};

// Couches GIBS : l'image de la Terre prise par la caméra de chaque satellite, jour par jour
const GIBS = (layer) => ({
  type: "imagery",
  layer,
  url: (date) => `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/${layer}/default/${date}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`,
});

// Satellites météo géostationnaires : une vraie photo de la Terre entière toutes les 10 minutes (NOAA)
const GOES = (sat, where) => ({
  type: "snapshot",
  title: "Caméra embarquée : image réelle",
  text: `Dernière photo de la Terre entière prise par l'imageur ABI de ${sat} (${where}), à 35 786 km d'altitude. Nouvelle image toutes les 10 minutes.`,
  image: `https://cdn.star.nesdis.noaa.gov/${sat.replace("-", "")}/ABI/FD/GEOCOLOR/1808x1808.jpg`,
  credit: "NOAA / NESDIS STAR",
});

export const CAMERAS = {
  "60133": GOES("GOES-19", "au-dessus des Amériques et de l'Atlantique"),
  "51850": GOES("GOES-18", "au-dessus du Pacifique"),
  "25544": {
    type: "live",
    title: "Caméra embarquée : direct vidéo réel",
    text: "Flux vidéo en direct de la chaîne YouTube officielle de la NASA. Quand l'ISS est dans l'ombre de la Terre ou en perte de signal, l'écran peut être noir ou afficher une autre diffusion.",
    embed: "https://www.youtube.com/embed/live_stream?channel=UCLA_DiR1FfKNvjuUpBHmylQ&autoplay=1&mute=1",
  },
  "25994": { ...GIBS("MODIS_Terra_CorrectedReflectance_TrueColor"), title: "Caméra embarquée : images réelles du jour", text: "Mosaïque des images prises par l'instrument MODIS de Terra pendant la journée choisie, en couleurs naturelles (résolution 250 m)." },
  "27424": { ...GIBS("MODIS_Aqua_CorrectedReflectance_TrueColor"), title: "Caméra embarquée : images réelles du jour", text: "Mosaïque des images prises par l'instrument MODIS d'Aqua pendant la journée choisie, en couleurs naturelles (résolution 250 m)." },
  "37849": { ...GIBS("VIIRS_SNPP_CorrectedReflectance_TrueColor"), title: "Caméra embarquée : images réelles du jour", text: "Images de l'instrument VIIRS de Suomi NPP pendant la journée choisie (résolution 375 m)." },
  "43013": { ...GIBS("VIIRS_NOAA20_CorrectedReflectance_TrueColor"), title: "Caméra embarquée : images réelles du jour", text: "Images de l'instrument VIIRS de NOAA-20 pendant la journée choisie (résolution 375 m)." },
  "54234": { ...GIBS("VIIRS_NOAA21_CorrectedReflectance_TrueColor"), title: "Caméra embarquée : images réelles du jour", text: "Images de l'instrument VIIRS de NOAA-21 pendant la journée choisie (résolution 375 m)." },
};

// Point lumineux doux pour chaque catégorie (un seul dessin partagé par des milliers d'objets).
// Correctif : la première version dessinait un petit satellite par objet -> 18 000 dessins illisibles.
export function markerIcon(color) {
  const s = 32;
  const c = document.createElement("canvas");
  c.width = c.height = s;
  const g = c.getContext("2d");
  const grad = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  grad.addColorStop(0, "#ffffff");
  grad.addColorStop(0.25, color);
  grad.addColorStop(0.55, color + "66");
  grad.addColorStop(1, color + "00");
  g.fillStyle = grad;
  g.fillRect(0, 0, s, s);
  return c.toDataURL();
}
