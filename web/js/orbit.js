// Module « Orbite » : globe 3D (CesiumJS) avec tout ce qui est suivi en orbite terrestre.
// Chaque position est calculée dans le navigateur avec SGP4 (satellite.js) à partir des TLE.
import { api, esc, safeUrl, fmtNum, fmtDate, fmtDateTime, fmtTime, loading, failed } from "./util.js";
import { icons } from "./icons.js";
import { MODELS, CAMERAS, markerIcon } from "./satmedia.js";
import { t } from "./i18n.js";

const CATS = {
  station: { label: "Stations spatiales", color: "#ffd166", px: 15 },
  science: { label: "Science / télescopes", color: "#c77dff", px: 11 },
  meteo: { label: "Météo", color: "#4cc9f0", px: 10 },
  observation: { label: "Observation de la Terre", color: "#57d68d", px: 10 },
  navigation: { label: "Navigation (GPS, Galileo…)", color: "#ff9f43", px: 10 },
  starlink: { label: "Starlink", color: "#9aa8c9", px: 6 },
  constellation: { label: "Autres constellations", color: "#9ad1d4", px: 7 },
  autre: { label: "Autres satellites", color: "#dfe6f5", px: 7 },
  debris: { label: "Débris", color: "#ff5c74", px: 5 },
};

const MU = 398600.4418;   // constante gravitationnelle de la Terre (km³/s²)
const R_EARTH = 6378.137; // km
const CHUNK = 3000;       // objets recalculés par image (fluidité avant tout)
const MODEL_RANGE = 4_000_000; // en dessous de 4 000 km de la caméra, on montre le vrai satellite

// Imagerie satellite haute résolution (jusqu'au niveau 19 : on voit les rues et les toits)
const ESRI = "https://services.arcgisonline.com/ArcGIS/rest/services";
const esriLayer = (path, credit) => new Cesium.UrlTemplateImageryProvider({
  url: `${ESRI}/${path}/MapServer/tile/{z}/{y}/{x}`,
  maximumLevel: 19,
  credit: credit ? new Cesium.Credit(credit, true) : undefined,
});

let viewer, billboards, cursor = 0, selected = null, appState;
let orbitEntity = null, labelEntity = null, observerEntity = null, modelEntity = null, photoEntity = null;
let placesLayer = null, roadsLayer = null, cameraLayer = null, buildings = null, pov = false;
let atmo = { layers: [], current: null, imagery: null, pin: null, lighting: true };
let records = [];
let companions = []; // objets amarrés au satellite choisi (ex. modules de l'ISS catalogués à part)
const visible = new Set(Object.keys(CATS).filter((c) => c !== "debris"));
const scratch = new Cesium.Cartesian3();
// Éclairage des modèles 3D : le rendu physique de Cesium les laisse presque noirs dans l'espace
// (pas de lumière ambiante). On garde leurs vraies couleurs et on éclaire : Soleil + lumière ambiante.
const MODEL_SHADER = new Cesium.CustomShader({
  lightingModel: Cesium.LightingModel.UNLIT,
  fragmentShaderText: `
    void fragmentMain(FragmentInput fsInput, inout czm_modelMaterial material) {
      vec3 n = normalize(fsInput.attributes.normalEC);
      float sun = abs(dot(n, normalize(czm_lightDirectionEC)));
      material.diffuse = material.diffuse * (0.45 + 0.75 * sun);
    }`,
});

const NEAR_FAR = new Cesium.NearFarScalar(1.0e6, 1.5, 3.5e7, 0.6); // les icônes grossissent quand on approche

// Temps simulé : on peut accélérer pour voir les orbites défiler
let speed = 1, simEpoch = Date.now(), realEpoch = Date.now();
const simNow = () => new Date(simEpoch + (Date.now() - realEpoch) * speed);

export async function init(state) {
  appState = state;
  viewer = new Cesium.Viewer("globe", {
    baseLayer: new Cesium.ImageryLayer(esriLayer("World_Imagery", "Imagerie © Esri, Maxar, Earthstar Geographics")),
    animation: false, timeline: false, baseLayerPicker: false, geocoder: false, homeButton: false,
    sceneModePicker: false, navigationHelpButton: false, fullscreenButton: false,
    infoBox: false, selectionIndicator: false,
    // Rendu à la vraie résolution de l'écran (sur un écran Retina, Cesium dessine sinon en demi-résolution)
    useBrowserRecommendedResolution: false,
    msaaSamples: 4,
  });
  const globe = viewer.scene.globe;
  globe.enableLighting = true;            // jour / nuit réels vus de l'espace
  // Correctif : près du sol, l'éclairage jour/nuit crée des bandes au niveau du terminateur.
  // On le fait disparaître en dessous de 6 500 km d'altitude (là où il n'apporte plus rien).
  globe.lightingFadeOutDistance = 6.5e6;
  globe.lightingFadeInDistance = 9.0e6;
  globe.maximumScreenSpaceError = 1.5;    // tuiles plus détaillées (2 par défaut)
  globe.tileCacheSize = 1000;
  // Correctif « textures qui bugguent » en suivant l'ISS : la caméra file à 7,6 km/s, les tuiles
  // n'ont pas le temps d'arriver. On précharge les tuiles voisines et on en charge plus à la fois.
  globe.preloadSiblings = true;
  globe.loadingDescendantLimit = 60;
  viewer.clock.shouldAnimate = false;
  placesLayer = viewer.imageryLayers.addImageryProvider(esriLayer("Reference/World_Boundaries_and_Places"));
  roadsLayer = viewer.imageryLayers.addImageryProvider(esriLayer("Reference/World_Transportation"));
  roadsLayer.show = false;

  if (new URLSearchParams(location.search).has("debug")) window.orbitraViewer = viewer; // diagnostic uniquement
  billboards = viewer.scene.primitives.add(new Cesium.BillboardCollection({ scene: viewer.scene }));
  viewer.camera.setView({ destination: Cesium.Cartesian3.fromDegrees(state.location.lon, state.location.lat - 20, 30_000_000) });

  placeObserver(state.location);
  bindControls();
  viewer.scene.preUpdate.addEventListener(frame);

  const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
  handler.setInputAction((e) => {
    const picked = viewer.scene.pick(e.position, 16, 16);
    const rec = picked?.id?.satrec ? picked.id : picked?.id?.orbitraRec;
    if (rec) { select(rec, false); return; }
    if (atmo.current) readAtmosphere(e.position); // pas de satellite cliqué : on lit la pollution à cet endroit
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

  setupBuildings(); // bâtiments 3D, seulement si une clé Cesium ion est configurée
  setupLaunchBridge();
  setupAtmosphere();
  await loadCatalog();
}

export function onLocation(state) { placeObserver(state.location); if (selected) renderCard(); }

async function loadCatalog() {
  const meta = document.getElementById("sat-meta");
  try {
    const data = await api("satellites");
    const images = Object.fromEntries(Object.entries(CATS).map(([k, c]) => [k, markerIcon(c.color)]));
    for (const s of data.satellites) {
      let satrec;
      try { satrec = satellite.twoline2satrec(s.l1, s.l2); } catch { continue; }
      if (satrec.error) continue;
      const cat = CATS[s.cat] ? s.cat : "autre";
      const rec = { ...s, cat, satrec };
      rec.bb = billboards.add({
        id: rec,
        image: images[cat],
        position: Cesium.Cartesian3.ZERO,
        width: CATS[cat].px,
        height: CATS[cat].px,
        scaleByDistance: NEAR_FAR,
        show: false,
      });
      records.push(rec);
    }
    document.getElementById("sat-count").textContent = fmtNum(records.length);
    meta.innerHTML = `Données : ${esc(data.source)} · mises à jour ${esc(fmtDateTime(data.updated))}` +
      (data.complete ? "" : "<br>Attention : catalogue partiel (CelesTrak indisponible)");
    renderCategories(data.categories);
    const iss = records.find((r) => r.id === "25544");
    if (iss) select(iss, false);
  } catch (err) {
    meta.innerHTML = `<span class="error">Catalogue indisponible : ${esc(err.message)}</span>`;
  }
}

// ---------- Calcul des positions ----------

function propagate(rec, date, gmst) {
  const pv = satellite.propagate(rec.satrec, date);
  const p = pv.position;
  if (!p || Number.isNaN(p.x)) return null;
  return { eci: p, vel: pv.velocity, ecf: satellite.eciToEcf(p, gmst) };
}

const toCartesian = (ecf, result) => Cesium.Cartesian3.fromElements(ecf.x * 1000, ecf.y * 1000, ecf.z * 1000, result);

function update(rec, date, gmst) {
  if (!visible.has(rec.cat) && rec !== selected) { rec.bb.show = false; return; }
  const st = propagate(rec, date, gmst);
  if (!st) { rec.bb.show = false; return; } // objet rentré dans l'atmosphère
  rec.bb.position = toCartesian(st.ecf, scratch);
  rec.bb.show = true;
  rec.state = st;
  if (rec === selected) {
    // vitesse dans le repère terrestre (différence finie sur 1 s) : sert à orienter le modèle 3D
    const later = new Date(+date + 1000);
    const st2 = propagate(rec, later, satellite.gstime(later));
    if (st2) rec.velEcf = new Cesium.Cartesian3((st2.ecf.x - st.ecf.x) * 1000, (st2.ecf.y - st.ecf.y) * 1000, (st2.ecf.z - st.ecf.z) * 1000);
  }
}

let lastCard = 0, lastOrbit = 0;
function frame() {
  const now = simNow();
  viewer.clock.currentTime = Cesium.JulianDate.fromDate(now);
  const n = records.length;
  if (!n) return;
  const gmst = satellite.gstime(now);
  for (let k = 0; k < Math.min(CHUNK, n); k++) {
    update(records[cursor], now, gmst);
    cursor = (cursor + 1) % n;
  }
  if (selected) {
    update(selected, now, gmst);
    if (pov) flyPov();
    const t = performance.now();
    if (t - lastCard > 500) { lastCard = t; renderLive(); }
    if (now - lastOrbit > 20000 || now < lastOrbit) { lastOrbit = +now; drawOrbit(); }
  }
}

// ---------- Sélection d'un objet ----------

function orbitalElements(rec) {
  const s = rec.satrec;
  const n = s.no / 60;                       // rad/s
  const a = Math.cbrt(MU / (n * n));         // demi-grand axe (3e loi de Kepler)
  const e = s.ecco;
  const periodMin = (2 * Math.PI) / s.no;
  const apogee = a * (1 + e) - R_EARTH;
  const perigee = a * (1 - e) - R_EARTH;
  let regime = "Orbite moyenne (MEO)";
  if (apogee < 2000) regime = "Orbite basse (LEO)";
  else if (e > 0.25) regime = "Orbite très elliptique (HEO)";
  else if (Math.abs(periodMin - 1436) < 15) regime = "Géostationnaire (GEO)";
  return { a, e, periodMin, apogee, perigee, regime, inclination: (s.inclo * 180) / Math.PI };
}

// Orientation du modèle : aligné sur sa direction de déplacement, « bas » vers la Terre
function orientationOf(rec) {
  return new Cesium.CallbackProperty(() => {
    const p = rec.bb.position, v = rec.velEcf;
    if (!v) return undefined;
    const enu = Cesium.Transforms.eastNorthUpToFixedFrame(p);
    const inv = Cesium.Matrix4.inverseTransformation(enu, new Cesium.Matrix4());
    const local = Cesium.Matrix4.multiplyByPointAsVector(inv, v, new Cesium.Cartesian3());
    const heading = Math.atan2(local.x, local.y);
    return Cesium.Transforms.headingPitchRollQuaternion(p, new Cesium.HeadingPitchRoll(heading - Math.PI / 2, 0, Math.PI / 2));
  }, false);
}

function setCompanions(rec) {
  for (const c of companions) c.bb.distanceDisplayCondition = undefined;
  companions = [];
  if (!rec || !MODELS[rec.id] || !rec.state) return;
  // Correctif : au démarrage, les positions des autres objets ne sont pas encore calculées
  // (l'ISS est sélectionnée avant le premier passage de la boucle). On les calcule ici.
  const now = simNow(), gmst = satellite.gstime(now);
  const p = toCartesian(rec.state.ecf);
  companions = records.filter((r) => {
    if (r === rec) return false;
    const st = propagate(r, now, gmst);
    return st && Cesium.Cartesian3.distance(toCartesian(st.ecf), p) < 5000;
  });
  for (const c of companions) c.bb.distanceDisplayCondition = new Cesium.DistanceDisplayCondition(MODEL_RANGE, Number.MAX_VALUE);
}

function clearSelectionEntities() {
  setCompanions(null);
  if (placesLayer) placesLayer.show = document.getElementById("layer-places").checked;
  if (billboards) billboards.show = true;
  for (const e of [labelEntity, modelEntity, photoEntity]) if (e) viewer.entities.remove(e);
  labelEntity = modelEntity = photoEntity = null;
  viewer.trackedEntity = undefined;
  setPov(false);
  setCameraLayer(null);
}

function select(rec, fly = true) {
  if (selected?.bb) { selected.bb.scale = 1; selected.bb.distanceDisplayCondition = undefined; }
  clearSelectionEntities();
  selected = rec;
  rec.bb.scale = 1.5;
  update(rec, simNow(), satellite.gstime(simNow()));
  const position = new Cesium.CallbackProperty(() => rec.bb.position, false);

  labelEntity = viewer.entities.add({
    position,
    label: {
      text: rec.name, font: "600 14px Space Grotesk, sans-serif", fillColor: Cesium.Color.WHITE,
      outlineColor: Cesium.Color.BLACK, outlineWidth: 4, style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      pixelOffset: new Cesium.Cartesian2(0, -30), disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
  });

  // Le vrai satellite : modèle 3D officiel de la NASA quand on s'approche
  if (MODELS[rec.id]) {
    modelEntity = viewer.entities.add({
      position,
      orientation: orientationOf(rec),
      model: {
        uri: MODELS[rec.id],
        minimumPixelSize: 90,
        customShader: MODEL_SHADER,
        maximumScale: 50000,
        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, MODEL_RANGE),
      },
      viewFrom: new Cesium.Cartesian3(-180, -260, 120),
    });
    modelEntity.orbitraRec = rec;
    rec.bb.distanceDisplayCondition = new Cesium.DistanceDisplayCondition(MODEL_RANGE, Number.MAX_VALUE);
    setCompanions(rec);
  }

  lastOrbit = 0;
  drawOrbit();
  renderCard();
  if (fly) {
    viewer.camera.flyTo({ destination: Cesium.Cartesian3.multiplyByScalar(rec.bb.position, 2.6, new Cesium.Cartesian3()), duration: 1.6 });
  }
}

// Sans modèle 3D : la vraie photo du satellite s'affiche quand on s'approche
function showPhoto(rec, url) {
  if (MODELS[rec.id] || !url || selected !== rec) return;
  photoEntity = viewer.entities.add({
    position: new Cesium.CallbackProperty(() => rec.bb.position, false),
    billboard: {
      image: url,
      scale: 0.55,
      pixelOffset: new Cesium.Cartesian2(0, -110),
      distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, MODEL_RANGE),
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
  });
}

function drawOrbit() {
  if (!selected) return;
  const { periodMin } = orbitalElements(selected);
  const start = simNow();
  const positions = [];
  const steps = 240;
  for (let k = 0; k <= steps; k++) {
    const t = new Date(+start + (k / steps) * periodMin * 60000);
    const st = propagate(selected, t, satellite.gstime(t));
    if (st) positions.push(toCartesian(st.ecf));
  }
  if (orbitEntity) viewer.entities.remove(orbitEntity);
  orbitEntity = viewer.entities.add({
    polyline: {
      positions, width: 2,
      material: new Cesium.PolylineGlowMaterialProperty({ glowPower: 0.2, color: Cesium.Color.fromCssColorString(CATS[selected.cat].color).withAlpha(0.9) }),
    },
  });
}

// ---------- Vue depuis le satellite ----------

function flyPov() {
  const p = selected.bb.position, v = selected.velEcf;
  if (!v || Cesium.Cartesian3.equals(p, Cesium.Cartesian3.ZERO)) return;
  const down = Cesium.Cartesian3.normalize(Cesium.Cartesian3.negate(p, new Cesium.Cartesian3()), new Cesium.Cartesian3());
  const fwd = Cesium.Cartesian3.normalize(v, new Cesium.Cartesian3());
  // caméra légèrement en arrière et au-dessus : on voit la Terre défiler sous le satellite
  const back = Cesium.Cartesian3.multiplyByScalar(fwd, -40_000, new Cesium.Cartesian3());
  const up = Cesium.Cartesian3.multiplyByScalar(down, -15_000, new Cesium.Cartesian3());
  const eye = Cesium.Cartesian3.add(Cesium.Cartesian3.add(p, back, new Cesium.Cartesian3()), up, new Cesium.Cartesian3());
  const dir = Cesium.Cartesian3.normalize(Cesium.Cartesian3.add(Cesium.Cartesian3.multiplyByScalar(down, 0.8, new Cesium.Cartesian3()), fwd, new Cesium.Cartesian3()), new Cesium.Cartesian3());
  viewer.camera.setView({ destination: eye, orientation: { direction: dir, up: Cesium.Cartesian3.negate(down, new Cesium.Cartesian3()) } });
}

function setPov(on) {
  const wasOn = pov;
  pov = on;
  viewer.scene.screenSpaceCameraController.enableInputs = !on;
  const btn = document.getElementById("sat-pov");
  if (btn) { btn.classList.toggle("primary", on); btn.innerHTML = on ? "Quitter la vue 3D" : `${icons.eye(14)} Vue 3D (reconstitution)`; }
  // on ne recule la caméra que si on sortait vraiment de la vue satellite
  if (wasOn && !on && selected?.bb) {
    viewer.camera.flyTo({ destination: Cesium.Cartesian3.multiplyByScalar(selected.bb.position, 2.6, new Cesium.Cartesian3()), duration: 1.2 });
  }
}

// ---------- Caméra du satellite (direct ou images du jour) ----------

function setCameraLayer(provider) {
  if (cameraLayer) { viewer.imageryLayers.remove(cameraLayer); cameraLayer = null; }
  if (!provider) return;
  cameraLayer = viewer.imageryLayers.addImageryProvider(provider);
  viewer.imageryLayers.raiseToTop(placesLayer);
}

function renderCamera(rec) {
  const cam = CAMERAS[rec.id];
  if (!cam) return "";
  if (cam.type === "live") {
    return `<div class="section-title">${esc(cam.title)}</div>
      <p class="small dim">${esc(cam.text)}</p>
      <div id="cam-live" class="row"><button class="btn primary" id="cam-live-btn">${icons.camera(14)} Ouvrir le direct</button>
        <button class="btn" id="cam-crew-btn">Photos de l'équipage et film du trajet</button></div>`;
  }
  if (cam.type === "snapshot") {
    return `<div class="section-title">${esc(cam.title)}</div>
      <p class="small dim">${esc(cam.text)}</p>
      <a href="${esc(safeUrl(cam.image))}" target="_blank" rel="noopener noreferrer"><img class="sat-photo cam-shot" id="cam-shot" src="${esc(safeUrl(cam.image))}?t=${Date.now()}" alt="Dernière image réelle de ${esc(rec.name)}" loading="lazy"></a>
      <p class="small dim" id="cam-time">Image : ${esc(cam.credit)}</p>`;
  }
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
  return `<div class="section-title">${esc(cam.title)}</div>
    <p class="small dim">${esc(cam.text)}</p>
    <div class="row">
      <input type="date" id="cam-date" value="${yesterday}" max="${yesterday}" min="2012-01-01" class="date-input">
      <button class="btn primary" id="cam-show">${icons.camera(14)} Afficher sur le globe</button>
    </div>`;
}

function bindCamera(rec) {
  const cam = CAMERAS[rec.id];
  if (!cam) return;
  if (cam.type === "live") {
    document.getElementById("cam-crew-btn").onclick = () => document.querySelector('#tabs [data-view="cameras"]').click();
    document.getElementById("cam-live-btn").onclick = () => {
      document.getElementById("cam-live").innerHTML = `<div class="video"><iframe src="${esc(safeUrl(cam.embed))}" title="Direct de l'ISS"
        allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe></div>`;
    };
    return;
  }
  if (cam.type === "snapshot") {
    // heure exacte de la prise de vue (en-tête Last-Modified du serveur de la NOAA)
    fetch(cam.image, { method: "HEAD" }).then((r) => {
      const when = r.headers.get("last-modified");
      const el = document.getElementById("cam-time");
      if (when && el) el.textContent = `Photo prise le ${fmtDateTime(new Date(when).toISOString())} · ${cam.credit}`;
    }).catch(() => {});
    return;
  }
  const btn = document.getElementById("cam-show");
  btn.onclick = () => {
    if (cameraLayer) { setCameraLayer(null); btn.innerHTML = `${icons.camera(14)} Afficher sur le globe`; return; }
    const date = document.getElementById("cam-date").value;
    setCameraLayer(new Cesium.UrlTemplateImageryProvider({ url: cam.url(date), maximumLevel: 9, credit: new Cesium.Credit("Images : NASA EOSDIS GIBS", true) }));
    btn.textContent = "Masquer ces images";
    const geo = Cesium.Cartographic.fromCartesian(rec.bb.position);
    viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromRadians(geo.longitude, geo.latitude, 9_000_000), duration: 1.5 });
  };
  document.getElementById("cam-date").onchange = () => { if (cameraLayer) { setCameraLayer(null); btn.click(); } };
}

// ---------- Fiche ----------

function renderCard() {
  const card = document.getElementById("sat-card");
  const rec = selected;
  const el = orbitalElements(rec);
  card.classList.remove("hidden");
  card.innerHTML = `
    <button class="card-close" aria-label="Fermer">×</button>
    <h2>${esc(rec.name)}</h2>
    <span class="tag" style="border-color:${CATS[rec.cat].color};color:${CATS[rec.cat].color}">${esc(CATS[rec.cat].label)}</span>
    ${MODELS[rec.id] ? `<span class="tag">Modèle 3D NASA</span>` : ""}
    <div class="row" style="margin-top:.7rem">
      <button class="btn" id="sat-follow">${icons.camera(14)} ${MODELS[rec.id] ? "Voir de près" : "Suivre"}</button>
      <button class="btn" id="sat-pov" title="Reconstitution 3D à partir de l'imagerie satellite : ce n'est PAS la caméra du satellite">${icons.eye(14)} Vue 3D (reconstitution)</button>
    </div>
    <div id="sat-info"><p class="small dim">Recherche de la fiche de mission…</p></div>
    <div id="sat-osint"></div>
    ${renderCamera(rec)}

    <div class="section-title">En direct</div>
    <dl class="kv" id="sat-live"></dl>

    <div class="section-title">Orbite</div>
    <dl class="kv">
      <dt>Type d'orbite</dt><dd>${esc(el.regime)}</dd>
      <dt>Un tour de Terre</dt><dd>${fmtNum(el.periodMin, 1)} min</dd>
      <dt>Tours par jour</dt><dd>${fmtNum(1440 / el.periodMin, 1)}</dd>
      <dt>Inclinaison</dt><dd>${fmtNum(el.inclination, 2)}°</dd>
      <dt>Périgée / apogée</dt><dd>${fmtNum(el.perigee)} / ${fmtNum(el.apogee)} km</dd>
      <dt>Excentricité</dt><dd>${el.e.toFixed(5)}</dd>
      <dt>N° NORAD</dt><dd>${esc(rec.id)}</dd>
    </dl>
    <button class="btn primary" id="sat-passes-btn">Passages au-dessus de moi</button>
    <div id="sat-passes"></div>`;
  loadInfo(rec);
  loadOsint(rec);
  bindCamera(rec);
  card.querySelector(".card-close").onclick = () => { card.classList.add("hidden"); clearSelectionEntities(); };
  card.querySelector("#sat-follow").onclick = (e) => {
    const target = modelEntity ?? labelEntity;
    const on = viewer.trackedEntity !== target;
    setPov(false);
    viewer.trackedEntity = on ? target : undefined;
    placesLayer.show = on ? false : document.getElementById("layer-places").checked;
    billboards.show = !on; // vue rapprochée : les 18 000 autres points disparaissent
    e.currentTarget.classList.toggle("primary", on);
  };
  card.querySelector("#sat-pov").onclick = () => { viewer.trackedEntity = undefined; setPov(!pov); };
  card.querySelector("#sat-passes-btn").onclick = () => loadPasses(rec);
  renderLive();
}

// Fiche de mission : pourquoi il est parti, depuis quand, ce qu'il récolte, quand ça finit
async function loadInfo(rec) {
  const box = document.getElementById("sat-info");
  let d;
  try {
    d = await api(`satellites/${encodeURIComponent(rec.id)}/info`);
  } catch (err) {
    box.innerHTML = `<p class="small dim">Fiche de mission indisponible (${esc(err.message)}).</p>`;
    return;
  }
  if (selected !== rec) return; // l'utilisateur a cliqué ailleurs entre-temps
  const wp = d.wikipedia, wd = d.wikidata, fam = d.family;
  const photo = wp?.thumbnail;
  showPhoto(rec, photo);
  const active = d.status === "En service" || d.status === "Mission prolongée";
  const end = d.decay_date
    ? `Rentré dans l'atmosphère le ${fmtDate(d.decay_date)}`
    : d.mission_end ? `${new Date(d.mission_end) > new Date() ? "Prévue le" : "Terminée le"} ${fmtDate(d.mission_end)}`
    : fam?.lifetime ?? (active ? "Toujours en activité, pas de date de fin annoncée" : "—");

  box.innerHTML = `
    ${photo ? `<img class="sat-photo" src="${esc(safeUrl(photo))}" alt="" loading="lazy" referrerpolicy="no-referrer">` : ""}
    ${d.status ? `<p class="small"><span class="status-dot ${active ? "on" : "off"}"></span>${esc(d.status)} · ${esc(d.type ?? "")}</p>` : ""}

    <div class="section-title">Sa mission</div>
    ${wd?.description ? `<p class="note"><strong>${esc(capitalize(wd.description))}.</strong></p>` : ""}
    ${fam?.mission ? `<p class="note">${esc(fam.mission)}</p>` : ""}
    ${wp?.extract ? `<p class="note small">${esc(truncate(wp.extract, 420))}</p>` : ""}
    ${!fam && !wp && !wd ? `<p class="note small dim">Aucune fiche publique détaillée pour cet objet (souvent le cas des satellites militaires ou commerciaux peu connus).</p>` : ""}

    ${fam?.collects ? `<div class="section-title">Ce qu'il fait / récolte</div><p class="note">${esc(fam.collects)}</p>` : ""}
    ${wd?.uses?.length ? `<p class="small dim">Usages : ${esc(wd.uses.join(", "))}</p>` : ""}

    <div class="section-title">Son histoire</div>
    <dl class="kv">
      <dt>Lancé le</dt><dd>${fmtDate(d.launch_date)}</dd>
      <dt>Depuis</dt><dd>${d.years_in_orbit != null ? `${fmtNum(d.years_in_orbit, 1)} ans` : "—"}</dd>
      <dt>Lancé depuis</dt><dd>${esc(d.launch_site ?? "—")}</dd>
      <dt>Pays / propriétaire</dt><dd>${esc(d.owner ?? "—")}</dd>
      ${wd?.operators?.length ? `<dt>Opérateur</dt><dd>${esc(wd.operators.join(", "))}</dd>` : ""}
      <dt>Taille</dt><dd>${esc(d.size ?? "—")}</dd>
      <dt>Désignation</dt><dd>${esc(d.object_id ?? "—")}</dd>
    </dl>
    <div class="section-title">Fin de mission</div>
    <p class="note small">${esc(end)}</p>
    ${wp?.url ? `<p class="small"><a href="${esc(safeUrl(wp.url))}" target="_blank" rel="noopener noreferrer">${icons.link(13)} Article Wikipédia complet</a></p>` : ""}
    <p class="sources">Sources : ${esc(d.sources.join(" · ") || "catalogue TLE")}${MODELS[rec.id] ? " · Modèle 3D : NASA" : ""}</p>`;
}

// Dossier OSINT : sources ouvertes (catalogue GCAT de J. McDowell + base radio SatNOGS)
async function loadOsint(rec) {
  const box = document.getElementById("sat-osint");
  let d;
  try { d = await api(`satellites/${encodeURIComponent(rec.id)}/osint`); } catch { return; }
  if (selected !== rec || (!d.gcat && !d.satnogs)) return;
  const g = d.gcat ?? {}, n = d.satnogs ?? {};
  const dims = g.dimensions_m ?? {};
  const size = [dims.length && `${fmtNum(dims.length, 1)} m de long`, dims.diameter && `${fmtNum(dims.diameter, 1)} m de diamètre`,
    dims.span && `${fmtNum(dims.span, 1)} m d'envergure`].filter(Boolean).join(", ");
  const radios = (n.radios ?? []).filter((r) => r.active).slice(0, 6);
  box.innerHTML = `
    <div class="section-title">Dossier OSINT (sources ouvertes)</div>
    ${g.user?.length ? `<p class="small"><span class="tag ${g.military ? "tag-mil" : ""}">${esc(g.user.join(" + "))}</span>${g.category ? ` <span class="tag">${esc(g.category)}</span>` : ""}</p>` : ""}
    <dl class="kv">
      ${g.manufacturer ? `<dt>Constructeur</dt><dd>${esc(g.manufacturer)}</dd>` : ""}
      ${g.owner ? `<dt>Exploitant</dt><dd>${esc(g.owner)}</dd>` : ""}
      ${g.program ? `<dt>Programme</dt><dd>${esc(g.program)}</dd>` : ""}
      ${g.bus ? `<dt>Plateforme</dt><dd>${esc(g.bus)}</dd>` : ""}
      ${g.mass_kg ? `<dt>Masse</dt><dd>${fmtNum(g.mass_kg)} kg${g.dry_mass_kg && g.dry_mass_kg !== g.mass_kg ? ` (${fmtNum(g.dry_mass_kg)} kg à vide)` : ""}</dd>` : ""}
      ${size ? `<dt>Dimensions</dt><dd>${esc(size)}</dd>` : ""}
      ${g.shape ? `<dt>Forme</dt><dd>${esc(g.shape)}</dd>` : ""}
      ${g.jcat ? `<dt>Déclaré à l'ONU</dt><dd>${g.un_registered ? esc(g.un_registration) : "non"}</dd>` : ""}
      ${n.countries ? `<dt>Pays (SatNOGS)</dt><dd>${esc(n.countries)}</dd>` : ""}
    </dl>
    ${radios.length ? `<div class="small dim" style="margin-bottom:.3rem">Émetteurs radio actifs (on peut les écouter avec une antenne et un récepteur SDR) :</div>
      <ul class="radios">${radios.map((r) => `<li><span class="mono">${fmtNum(r.mhz, 3)} MHz</span> ${esc(r.mode ?? "")} · ${esc(r.label ?? "")}</li>`).join("")}</ul>` : ""}
    <p class="sources">${esc(d.sources.join(" · "))}${n.page ? ` · <a href="${esc(safeUrl(n.page))}" target="_blank" rel="noopener noreferrer">fiche SatNOGS</a>` : ""}</p>`;
}

const capitalize = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const truncate = (s, n) => (s.length > n ? `${s.slice(0, s.lastIndexOf(" ", n))}…` : s);

function renderLive() {
  const box = document.getElementById("sat-live");
  if (!box || !selected?.state) return;
  const now = simNow();
  const geo = satellite.eciToGeodetic(selected.state.eci, satellite.gstime(now));
  const v = selected.state.vel;
  const speedKms = Math.hypot(v.x, v.y, v.z);
  box.innerHTML = `
    <dt>Altitude</dt><dd>${fmtNum(geo.height)} km</dd>
    <dt>Vitesse</dt><dd>${fmtNum(speedKms, 2)} km/s · ${fmtNum(speedKms * 3600)} km/h</dd>
    <dt>Survole</dt><dd>${fmtNum(satellite.degreesLat(geo.latitude), 2)}°, ${fmtNum(satellite.degreesLong(geo.longitude), 2)}°</dd>`;
}

async function loadPasses(rec) {
  const box = document.getElementById("sat-passes");
  loading(box, "Calcul des passages sur 3 jours…");
  try {
    const { lat, lon, alt } = appState.location;
    const data = await api(`satellites/${encodeURIComponent(rec.id)}/passes`, { lat, lon, alt });
    if (!data.passes.length) { box.innerHTML = `<p class="small dim">Aucun passage à plus de 10° d'élévation dans les 3 prochains jours.</p>`; return; }
    box.innerHTML = `<h3>Prochains passages</h3>` + data.passes.slice(0, 8).map((p) => `
      <div class="tile" style="padding:.6rem;margin:.4rem 0">
        <div class="row"><strong>${esc(fmtDateTime(p.rise))}</strong><span class="spacer"></span>
          ${p.visible ? '<span class="rating excellente">visible à l\'œil nu</span>' : '<span class="tag">non visible</span>'}</div>
        <div class="small dim">${esc(p.rise_dir)} → ${esc(p.max_dir)} (${p.max_elevation}°) → ${esc(p.set_dir)} · ${Math.round(p.duration_s / 60)} min · fin ${esc(fmtTime(p.set))}</div>
      </div>`).join("");
  } catch (err) { failed(box, err); }
}

// ---------- Liens depuis les autres onglets (lancements…) ----------

let launchEntities = [];

// Point à une distance donnée le long d'un grand cercle (trigonométrie sphérique)
function destination(lat, lon, azimuthDeg, km) {
  const R = 6371, d = km / R, az = Cesium.Math.toRadians(azimuthDeg);
  const φ1 = Cesium.Math.toRadians(lat), λ1 = Cesium.Math.toRadians(lon);
  const φ2 = Math.asin(Math.sin(φ1) * Math.cos(d) + Math.cos(φ1) * Math.sin(d) * Math.cos(az));
  const λ2 = λ1 + Math.atan2(Math.sin(az) * Math.sin(d) * Math.cos(φ1), Math.cos(d) - Math.sin(φ1) * Math.sin(φ2));
  return [Cesium.Math.toDegrees(λ2), Cesium.Math.toDegrees(φ2)];
}

function showLaunch({ lat, lon, name, inclination }) {
  for (const e of launchEntities) viewer.entities.remove(e);
  launchEntities = [viewer.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    point: { pixelSize: 12, color: Cesium.Color.fromCssColorString("#ff9f43"), outlineColor: Cesium.Color.WHITE, outlineWidth: 2 },
    label: { text: name, font: "600 13px Space Grotesk, sans-serif", pixelOffset: new Cesium.Cartesian2(0, -22), fillColor: Cesium.Color.WHITE,
      outlineColor: Cesium.Color.BLACK, outlineWidth: 4, style: Cesium.LabelStyle.FILL_AND_OUTLINE, disableDepthTestDistance: Number.POSITIVE_INFINITY },
  })];
  if (inclination != null) {
    // Plan de l'orbite atteinte : le grand cercle incliné de i qui passe par le pas de tir.
    // Azimut de tir : sin(Az) = cos(i) / cos(latitude) (impossible si i < latitude : on vise plein est)
    const ratio = Math.cos(Cesium.Math.toRadians(inclination)) / Math.cos(Cesium.Math.toRadians(lat));
    const az = Math.abs(ratio) <= 1 ? Cesium.Math.toDegrees(Math.asin(ratio)) : 90;
    const pts = [];
    for (let km = 0; km <= 40030; km += 400) pts.push(...destination(lat, lon, az, km));
    launchEntities.push(viewer.entities.add({
      polyline: { positions: Cesium.Cartesian3.fromDegreesArray(pts), width: 2,
        material: new Cesium.PolylineDashMaterialProperty({ color: Cesium.Color.fromCssColorString("#ff9f43"), dashLength: 18 }) },
    }));
  }
  viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(lon, lat - 6, inclination != null ? 9_000_000 : 1_500_000), duration: 2 });
}

function setupLaunchBridge() {
  window.addEventListener("orbitra:launch", (e) => showLaunch(e.detail));
  window.addEventListener("orbitra:select-sat", async (e) => {
    for (let i = 0; i < 60 && !records.length; i++) await new Promise((r) => setTimeout(r, 500)); // catalogue en cours de chargement
    const rec = records.find((r) => r.id === String(e.detail.norad));
    if (rec) select(rec);
    else alert(t("Cet objet n'est pas (ou plus) dans le catalogue des objets suivis : il est peut-être retombé ou trop récent."));
  });
}

// ---------- Pollution vue de l'espace (NASA GIBS) ----------

const SUP = { "-": "⁻", "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹" };
function fmtValue(v) {
  if (v == null) return "—";
  if (Math.abs(v) >= 1e5) {
    const exp = Math.floor(Math.log10(Math.abs(v)));
    return `${fmtNum(v / 10 ** exp, 1)} × 10${String(exp).replace(/./g, (c) => SUP[c])}`;
  }
  return fmtNum(v, Math.abs(v) < 10 ? 2 : 0);
}

async function setupAtmosphere() {
  const sel = document.getElementById("atmo-layer");
  try { atmo.layers = await api("atmosphere/layers"); } catch { sel.disabled = true; return; }
  sel.innerHTML = `<option value="">Aucune</option>` + atmo.layers.map((l) =>
    `<option value="${esc(l.key)}">${esc(l.formula)} · ${esc(l.name)} (${esc(l.satellite)})</option>`).join("");
  const date = document.getElementById("atmo-date");
  sel.onchange = () => {
    atmo.current = atmo.layers.find((l) => l.key === sel.value) ?? null;
    if (atmo.current) { date.value = atmo.current.latest; date.max = atmo.current.latest; date.min = atmo.current.first; }
    showAtmosphere();
  };
  date.onchange = showAtmosphere;
  document.getElementById("atmo-avg").onchange = showAtmosphere;
  document.getElementById("atmo-opacity").oninput = (e) => { if (atmo.imagery) atmo.imagery.alpha = +e.target.value; };
}

function showAtmosphere() {
  const l = atmo.current;
  if (atmo.imagery) { viewer.imageryLayers.remove(atmo.imagery); atmo.imagery = null; }
  if (atmo.pin) { viewer.entities.remove(atmo.pin); atmo.pin = null; }
  document.getElementById("atmo-controls").classList.toggle("hidden", !l);
  if (!l) { viewer.scene.globe.enableLighting = document.getElementById("layer-light").checked; return; }
  const date = document.getElementById("atmo-date").value || l.latest;
  const avg = document.getElementById("atmo-avg").checked;
  atmo.imagery = viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
    // moyenne sur 7 jours calculée par notre serveur (comble les trous des nuages), ou la journée brute de la NASA
    url: avg ? `/api/atmosphere/tile/${l.key}/${date}/{z}/{y}/{x}.png?days=7` : l.tile_url.replace("{date}", date),
    maximumLevel: 6,
    credit: new Cesium.Credit(`Mesures : NASA GIBS · ${l.satellite} / ${l.instrument}`, true),
  }));
  atmo.imagery.alpha = +document.getElementById("atmo-opacity").value;
  viewer.imageryLayers.raiseToTop(placesLayer);
  viewer.scene.globe.enableLighting = false; // la nuit assombrirait les mesures
  document.getElementById("atmo-info").innerHTML = `
    <img class="legend" src="${esc(safeUrl(l.legend))}" alt="Légende ${esc(l.formula)}">
    <p class="small dim" style="margin:.2rem 0">Unité : ${esc(l.units)} · ${esc(l.satellite)}, instrument ${esc(l.instrument)}${document.getElementById("atmo-avg").checked ? ` · moyenne des 7 jours précédant la date${l.fades_background ? " · le niveau de fond est laissé transparent" : ""}` : " · une seule journée"}</p>
    <p class="note small">${esc(l.what)}</p>
    <p class="small dim">${esc(l.health)}</p>
    <p class="small"><strong>Clique sur le globe</strong> pour lire la valeur mesurée, ou va voir :</p>
    <div class="chips">${l.hotspots.map((h, i) => `<button class="chip" data-h="${i}">${esc(h.name)}</button>`).join("")}</div>
    <div id="atmo-value"></div>`;
  document.querySelector("#atmo-info .chips").onclick = (e) => {
    const b = e.target.closest("[data-h]");
    if (!b) return;
    const h = l.hotspots[+b.dataset.h];
    viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(h.lon, h.lat - 8, 3_200_000),
      orientation: { pitch: Cesium.Math.toRadians(-65) }, duration: 2,
      complete: () => readAtmosphere(null, h.lat, h.lon) });
  };
}

async function readAtmosphere(screenPos, lat, lon) {
  if (screenPos) {
    const cart = viewer.camera.pickEllipsoid(screenPos, viewer.scene.globe.ellipsoid);
    if (!cart) return;
    const geo = Cesium.Cartographic.fromCartesian(cart);
    lat = Cesium.Math.toDegrees(geo.latitude);
    lon = Cesium.Math.toDegrees(geo.longitude);
  }
  const l = atmo.current, box = document.getElementById("atmo-value");
  box.innerHTML = `<div class="atmo-value dim">Lecture de la mesure…</div>`;
  let v;
  try {
    v = await api("atmosphere/value", { key: l.key, date: document.getElementById("atmo-date").value, lat: lat.toFixed(4), lon: lon.toFixed(4) });
  } catch (err) { box.innerHTML = `<div class="atmo-value error">${esc(err.message)}</div>`; return; }
  const where = `${fmtNum(lat, 2)}°, ${fmtNum(lon, 2)}°`;
  const text = v.found ? `${fmtValue(v.value)} ${v.units === "sans unité" ? "" : t(v.units)}`.trim() : t("pas de mesure");
  if (atmo.pin) viewer.entities.remove(atmo.pin);
  atmo.pin = viewer.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    point: { pixelSize: 9, color: Cesium.Color.WHITE, outlineColor: Cesium.Color.BLACK, outlineWidth: 2 },
    label: { text: `${l.formula} : ${text}`, font: "600 13px Space Grotesk, sans-serif", pixelOffset: new Cesium.Cartesian2(0, -20),
      fillColor: Cesium.Color.WHITE, outlineColor: Cesium.Color.BLACK, outlineWidth: 4, style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      disableDepthTestDistance: Number.POSITIVE_INFINITY },
  });
  box.innerHTML = v.found ? `<div class="atmo-value">
      <div class="big">${esc(l.formula)} : ${esc(text)}</div>
      <div>Niveau : <strong>${esc(v.level ?? "—")}</strong></div>
      <div class="small dim">${esc(where)} · mesure du ${esc(fmtDate(v.date))}${v.days_before ? ` (${v.days_before} j avant la date choisie)` : ""}${v.distance_km ? ` · à ${fmtNum(v.distance_km, 1)} km du point` : ""}</div>
      <div class="small dim">Intervalle exact de la table NASA : ${fmtValue(v.low)} à ${fmtValue(v.high)}</div>
    </div>` : `<div class="atmo-value"><div>${esc(where)}</div><div class="small dim">${esc(v.reason)}</div></div>`;
}

// ---------- Bâtiments 3D (optionnel) ----------

// Google Photorealistic 3D Tiles via Cesium ion : demande une clé gratuite (variable CESIUM_ION_TOKEN côté serveur).
async function setupBuildings() {
  let config;
  try { config = await api("config"); } catch { return; }
  if (!config.cesium_ion_token) return;
  Cesium.Ion.defaultAccessToken = config.cesium_ion_token;
  const toggle = document.getElementById("layer-buildings");
  toggle.closest("label").classList.remove("hidden");
  toggle.onchange = async () => {
    if (toggle.checked && !buildings) {
      try {
        buildings = await Cesium.createGooglePhotorealistic3DTileset();
        viewer.scene.primitives.add(buildings);
      } catch (err) {
        toggle.checked = false;
        alert(`Bâtiments 3D indisponibles : ${err.message}`);
        return;
      }
    }
    if (buildings) buildings.show = toggle.checked;
    viewer.scene.globe.show = !toggle.checked; // les tuiles 3D remplacent le globe
  };
}

// ---------- Interface ----------

function renderCategories(counts) {
  const box = document.getElementById("sat-cats");
  box.innerHTML = Object.entries(CATS).map(([key, c]) => `
    <label><input type="checkbox" data-cat="${key}" ${visible.has(key) ? "checked" : ""}>
      <span class="dot" style="background:${c.color}"></span>${esc(c.label)}<span class="n">${fmtNum(counts[key] ?? 0)}</span></label>`).join("");
  box.onchange = (e) => {
    const cat = e.target.dataset.cat;
    if (e.target.checked) visible.add(cat); else visible.delete(cat);
    if (!e.target.checked) for (const r of records) if (r.cat === cat && r !== selected) r.bb.show = false;
  };
}

function bindControls() {
  const input = document.getElementById("sat-search");
  const list = document.getElementById("sat-results");
  input.addEventListener("input", () => {
    const q = input.value.trim().toUpperCase();
    if (q.length < 2) { list.innerHTML = ""; return; }
    const hits = records
      .filter((r) => r.id === q || r.name.toUpperCase().includes(q))
      .sort((a, b) => (b.name.toUpperCase().startsWith(q) - a.name.toUpperCase().startsWith(q)) || a.name.length - b.name.length)
      .slice(0, 12);
    list.innerHTML = hits.map((r, i) => `<li data-i="${i}"><span>${esc(r.name)}</span><span class="mono">${esc(r.id)}</span></li>`).join("")
      || `<li class="dim">Aucun résultat</li>`;
    list.onclick = (e) => {
      const li = e.target.closest("li[data-i]");
      if (li) { select(hits[+li.dataset.i]); list.innerHTML = ""; input.value = ""; }
    };
  });

  for (const b of document.querySelectorAll("#orbit-panel [data-speed]")) {
    b.addEventListener("click", () => {
      const s = +b.dataset.speed;
      if (s === 0) { simEpoch = Date.now(); speed = 1; } else { simEpoch = +simNow(); speed = s; }
      realEpoch = Date.now();
      for (const o of document.querySelectorAll("#orbit-panel [data-speed]")) o.classList.toggle("active", +o.dataset.speed === (s || 1));
    });
  }

  document.getElementById("layer-places").onchange = (e) => { placesLayer.show = e.target.checked; };
  document.getElementById("layer-roads").onchange = (e) => { roadsLayer.show = e.target.checked; };
  document.getElementById("layer-light").onchange = (e) => { viewer.scene.globe.enableLighting = e.target.checked; };
  document.getElementById("zoom-home").onclick = () => {
    setPov(false);
    viewer.trackedEntity = undefined;
    const { lon, lat } = appState.location;
    viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(lon, lat - 0.012, 1800), orientation: { pitch: Cesium.Math.toRadians(-50) }, duration: 3 });
  };
  document.getElementById("zoom-space").onclick = () => {
    setPov(false);
    viewer.trackedEntity = undefined;
    const { lon, lat } = appState.location;
    viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(lon, lat - 20, 30_000_000), duration: 2.5 });
  };
}

function placeObserver(loc) {
  if (observerEntity) viewer.entities.remove(observerEntity);
  observerEntity = viewer.entities.add({
    position: Cesium.Cartesian3.fromDegrees(loc.lon, loc.lat),
    point: { pixelSize: 9, color: Cesium.Color.fromCssColorString("#6ea8ff"), outlineColor: Cesium.Color.WHITE, outlineWidth: 2, heightReference: Cesium.HeightReference.CLAMP_TO_GROUND },
    label: { text: t("Vous"), font: "12px Space Grotesk, sans-serif", pixelOffset: new Cesium.Cartesian2(0, -16), fillColor: Cesium.Color.WHITE, outlineColor: Cesium.Color.BLACK, outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE },
  });
}
