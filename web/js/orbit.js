// Module « Orbite » : globe 3D (CesiumJS) avec tout ce qui est suivi en orbite terrestre.
// Chaque position est calculée dans le navigateur avec SGP4 (satellite.js) à partir des TLE.
import { api, esc, safeUrl, fmtNum, fmtDate, fmtDateTime, fmtTime, loading, failed } from "./util.js";
import { icons } from "./icons.js";

const CATS = {
  station: { label: "Stations spatiales", color: "#ffd166", size: 7 },
  science: { label: "Science / télescopes", color: "#c77dff", size: 4 },
  meteo: { label: "Météo", color: "#4cc9f0", size: 3.5 },
  observation: { label: "Observation de la Terre", color: "#57d68d", size: 3 },
  navigation: { label: "Navigation (GPS, Galileo…)", color: "#ff9f43", size: 3.5 },
  starlink: { label: "Starlink", color: "#7f8fb5", size: 1.8 },
  constellation: { label: "Autres constellations", color: "#9ad1d4", size: 2.2 },
  autre: { label: "Autres satellites", color: "#dfe6f5", size: 2.2 },
  debris: { label: "Débris", color: "#ff5c74", size: 1.6 },
};

const MU = 398600.4418;   // constante gravitationnelle de la Terre (km³/s²)
const R_EARTH = 6378.137; // km
const CHUNK = 3000;       // objets recalculés par image (fluidité avant tout)

let viewer, points, cursor = 0, selected = null, orbitEntity = null, labelEntity = null, observerEntity = null;
let records = [];
let appState;
const visible = new Set(Object.keys(CATS).filter((c) => c !== "debris"));
const scratch = new Cesium.Cartesian3();

// Temps simulé : on peut accélérer pour voir les orbites défiler
let speed = 1, simEpoch = Date.now(), realEpoch = Date.now();
const simNow = () => new Date(simEpoch + (Date.now() - realEpoch) * speed);

export async function init(state) {
  appState = state;
  viewer = new Cesium.Viewer("globe", {
    baseLayer: Cesium.ImageryLayer.fromProviderAsync(
      Cesium.TileMapServiceImageryProvider.fromUrl(Cesium.buildModuleUrl("Assets/Textures/NaturalEarthII")),
    ),
    animation: false, timeline: false, baseLayerPicker: false, geocoder: false, homeButton: false,
    sceneModePicker: false, navigationHelpButton: false, fullscreenButton: false,
    infoBox: false, selectionIndicator: false,
  });
  viewer.scene.globe.enableLighting = true; // jour / nuit réels
  viewer.clock.shouldAnimate = false;
  points = viewer.scene.primitives.add(new Cesium.PointPrimitiveCollection());
  viewer.camera.setView({ destination: Cesium.Cartesian3.fromDegrees(state.location.lon, state.location.lat - 20, 30_000_000) });

  placeObserver(state.location);
  bindControls();
  viewer.scene.preUpdate.addEventListener(frame);

  const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
  handler.setInputAction((e) => {
    const picked = viewer.scene.pick(e.position, 14, 14);
    if (picked?.id?.satrec) select(picked.id, false);
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

  await loadCatalog();
}

export function onLocation(state) { placeObserver(state.location); if (selected) renderCard(); }

async function loadCatalog() {
  const meta = document.getElementById("sat-meta");
  try {
    const data = await api("satellites");
    for (const s of data.satellites) {
      let satrec;
      try { satrec = satellite.twoline2satrec(s.l1, s.l2); } catch { continue; }
      if (satrec.error) continue;
      const cat = CATS[s.cat] ? s.cat : "autre";
      const rec = { ...s, cat, satrec };
      rec.point = points.add({
        id: rec,
        position: Cesium.Cartesian3.ZERO,
        pixelSize: CATS[cat].size,
        color: Cesium.Color.fromCssColorString(CATS[cat].color),
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

function update(rec, date, gmst) {
  if (!visible.has(rec.cat) && rec !== selected) { rec.point.show = false; return; }
  const st = propagate(rec, date, gmst);
  if (!st) { rec.point.show = false; return; } // objet rentré dans l'atmosphère
  rec.point.position = Cesium.Cartesian3.fromElements(st.ecf.x * 1000, st.ecf.y * 1000, st.ecf.z * 1000, scratch);
  rec.point.show = true;
  rec.state = st;
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
  const intl = rec.l1.slice(9, 17).trim(); // ex. 98067A = 67e lancement de 1998, objet A
  const yy = parseInt(intl.slice(0, 2), 10);
  const launchYear = Number.isNaN(yy) ? null : (yy < 57 ? 2000 + yy : 1900 + yy);
  return { a, e, periodMin, apogee, perigee, regime, inclination: (s.inclo * 180) / Math.PI, intl, launchYear };
}

function select(rec, fly = true) {
  if (selected?.point) selected.point.pixelSize = CATS[selected.cat].size;
  selected = rec;
  rec.point.pixelSize = 12;
  rec.point.outlineColor = Cesium.Color.WHITE;
  rec.point.outlineWidth = 2;
  update(rec, simNow(), satellite.gstime(simNow()));

  if (labelEntity) viewer.entities.remove(labelEntity);
  labelEntity = viewer.entities.add({
    position: new Cesium.CallbackProperty(() => rec.point.position, false),
    label: {
      text: rec.name, font: "13px Space Grotesk, sans-serif", fillColor: Cesium.Color.WHITE,
      outlineColor: Cesium.Color.BLACK, outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      pixelOffset: new Cesium.Cartesian2(0, -18), disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
  });
  lastOrbit = 0;
  drawOrbit();
  renderCard();
  if (fly) {
    viewer.camera.flyTo({ destination: Cesium.Cartesian3.multiplyByScalar(rec.point.position, 2.6, new Cesium.Cartesian3()), duration: 1.6 });
  }
}

function drawOrbit() {
  if (!selected) return;
  const { periodMin } = orbitalElements(selected);
  const start = simNow();
  const positions = [];
  const steps = 200;
  for (let k = 0; k <= steps; k++) {
    const t = new Date(+start + (k / steps) * periodMin * 60000);
    const st = propagate(selected, t, satellite.gstime(t));
    if (st) positions.push(new Cesium.Cartesian3(st.ecf.x * 1000, st.ecf.y * 1000, st.ecf.z * 1000));
  }
  if (orbitEntity) viewer.entities.remove(orbitEntity);
  orbitEntity = viewer.entities.add({
    polyline: {
      positions, width: 1.6,
      material: new Cesium.PolylineGlowMaterialProperty({ glowPower: 0.2, color: Cesium.Color.fromCssColorString(CATS[selected.cat].color).withAlpha(0.9) }),
    },
  });
}

function renderCard() {
  const card = document.getElementById("sat-card");
  const rec = selected;
  const el = orbitalElements(rec);
  card.classList.remove("hidden");
  card.innerHTML = `
    <button class="card-close" aria-label="Fermer">×</button>
    <h2>${esc(rec.name)}</h2>
    <span class="tag" style="border-color:${CATS[rec.cat].color};color:${CATS[rec.cat].color}">${esc(CATS[rec.cat].label)}</span>
    <div id="sat-info"><p class="small dim">Recherche de la fiche de mission…</p></div>

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
    <div class="row">
      <button class="btn" id="sat-follow">${icons.camera(14)} Suivre</button>
      <button class="btn primary" id="sat-passes-btn">Passages au-dessus de moi</button>
    </div>
    <div id="sat-passes"></div>`;
  loadInfo(rec);
  card.querySelector(".card-close").onclick = () => { card.classList.add("hidden"); viewer.trackedEntity = undefined; };
  card.querySelector("#sat-follow").onclick = (e) => {
    const on = viewer.trackedEntity !== labelEntity;
    viewer.trackedEntity = on ? labelEntity : undefined;
    e.target.classList.toggle("primary", on);
  };
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
    <p class="sources">Sources : ${esc(d.sources.join(" · ") || "catalogue TLE")}</p>`;
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

// ---------- Interface ----------

function renderCategories(counts) {
  const box = document.getElementById("sat-cats");
  box.innerHTML = Object.entries(CATS).map(([key, c]) => `
    <label><input type="checkbox" data-cat="${key}" ${visible.has(key) ? "checked" : ""}>
      <span class="dot" style="background:${c.color}"></span>${esc(c.label)}<span class="n">${fmtNum(counts[key] ?? 0)}</span></label>`).join("");
  box.onchange = (e) => {
    const cat = e.target.dataset.cat;
    if (e.target.checked) visible.add(cat); else visible.delete(cat);
    if (!e.target.checked) for (const r of records) if (r.cat === cat && r !== selected) r.point.show = false;
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
}

function placeObserver(loc) {
  if (observerEntity) viewer.entities.remove(observerEntity);
  observerEntity = viewer.entities.add({
    position: Cesium.Cartesian3.fromDegrees(loc.lon, loc.lat),
    point: { pixelSize: 8, color: Cesium.Color.fromCssColorString("#6ea8ff"), outlineColor: Cesium.Color.WHITE, outlineWidth: 2 },
    label: { text: "Vous", font: "12px Space Grotesk, sans-serif", pixelOffset: new Cesium.Cartesian2(0, -16), fillColor: Cesium.Color.WHITE, outlineColor: Cesium.Color.BLACK, outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE },
  });
}
