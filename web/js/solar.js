// Module « Système solaire » : planètes, comètes, astéroïdes et visiteurs interstellaires en 3D.
// Les positions viennent de l'API (VSOP87 pour les planètes, Kepler pour le reste).
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CSS2DRenderer, CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import { api, esc, fmtNum, fmtDate, failed } from "./util.js";

const AU = 10; // 1 unité astronomique = 10 unités 3D
const TYPE_COLORS = { comete: "#7fe7ff", asteroide: "#b9a38a", interstellaire: "#ff7ad9" };
const TYPE_LABELS = { comete: "Comète", asteroide: "Astéroïde", interstellaire: "Objet interstellaire" };

let renderer, labels, scene, camera, controls, host;
let orbitsData, bodies = new Map(); // nom -> { mesh, line, info, pos }
let compressed = true, offsetDays = 0, playing = null, pending = false, queued = false, selectedName = null;

// Échelle compressée : r -> √r, pour voir Mercure ET Neptune sur le même écran
function toScene([x, y, z]) {
  const r = Math.hypot(x, y, z) || 1e-9;
  const k = compressed ? (Math.sqrt(r) / r) * AU * 1.6 : AU;
  // écliptique (x, y, z) -> Three.js (x, z, -y) : le plan de l'écliptique devient « le sol »
  return new THREE.Vector3(x * k, z * k, -y * k);
}

export async function init() {
  host = document.getElementById("solar");
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  host.appendChild(renderer.domElement);
  labels = new CSS2DRenderer();
  labels.domElement.style.position = "absolute";
  labels.domElement.style.inset = "0";
  labels.domElement.style.pointerEvents = "none";
  host.appendChild(labels.domElement);

  scene = new THREE.Scene();
  scene.background = new THREE.Color("#03040a");
  camera = new THREE.PerspectiveCamera(50, 1, 0.01, 5000);
  camera.position.set(0, 120, 160);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  addStars();
  const sun = new THREE.Mesh(new THREE.SphereGeometry(1.4, 32, 16), new THREE.MeshBasicMaterial({ color: "#ffd56b" }));
  sun.add(new THREE.Mesh(new THREE.SphereGeometry(2.2, 32, 16), new THREE.MeshBasicMaterial({ color: "#ffb347", transparent: true, opacity: 0.12, blending: THREE.AdditiveBlending, depthWrite: false })));
  scene.add(sun);
  addLabel(sun, "Soleil");

  new ResizeObserver(resize).observe(host);
  resize();
  renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); labels.render(scene, camera); });
  renderer.domElement.addEventListener("click", pick);
  bindControls();

  try {
    orbitsData = await api("solar-system/orbits");
    build();
    await refresh();
  } catch (err) {
    failed(document.getElementById("solar-list"), err);
  }
}

export function onShow() { resize(); }

function resize() {
  const w = host.clientWidth, h = host.clientHeight;
  if (!w || !h) return;
  renderer.setSize(w, h);
  labels.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}

function addStars() {
  const n = 4000, pos = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const v = new THREE.Vector3().randomDirection().multiplyScalar(1500 + Math.random() * 1500);
    pos.set([v.x, v.y, v.z], i * 3);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  scene.add(new THREE.Points(g, new THREE.PointsMaterial({ color: "#c9d4ff", size: 1.6, sizeAttenuation: false })));
}

function addLabel(obj, text, cls = "") {
  const div = document.createElement("div");
  div.className = `label3d ${cls}`;
  div.textContent = text;
  obj.add(new CSS2DObject(div));
}

function lineFor(points, color, opacity) {
  const g = new THREE.BufferGeometry().setFromPoints(points.map(toScene));
  return new THREE.Line(g, new THREE.LineBasicMaterial({ color, transparent: true, opacity }));
}

function build() {
  for (const b of bodies.values()) { scene.remove(b.mesh); scene.remove(b.line); }
  bodies.clear();

  for (const p of orbitsData.planets) {
    const size = 0.35 + Math.log10(p.radius_km / 2000) * 0.45;
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(size, 24, 12), new THREE.MeshBasicMaterial({ color: p.color }));
    if (p.name === "Saturne") {
      const ring = new THREE.Mesh(new THREE.RingGeometry(size * 1.4, size * 2.2, 48), new THREE.MeshBasicMaterial({ color: "#d9c58f", side: THREE.DoubleSide, transparent: true, opacity: 0.55 }));
      ring.rotation.x = Math.PI / 2.4;
      mesh.add(ring);
    }
    addLabel(mesh, p.name);
    const line = lineFor(p.orbit, p.color, 0.35);
    scene.add(mesh, line);
    bodies.set(p.name, { mesh, line, info: { ...p, kind: "planete" } });
  }

  for (const s of orbitsData.small_bodies) {
    const color = TYPE_COLORS[s.type] ?? "#ccc";
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.16, 12, 8), new THREE.MeshBasicMaterial({ color }));
    addLabel(mesh, shortName(s.name), "small-body");
    const line = lineFor(s.orbit, color, s.type === "asteroide" ? 0.22 : 0.4);
    scene.add(mesh, line);
    bodies.set(s.name, { mesh, line, info: { ...s, kind: s.type } });
  }
  renderList();
}

const shortName = (n) => n.replace(/^\s*\d+\s+/, "").replace(/\s*\(.*\)\s*$/, "").trim() || n;

async function refresh() {
  if (pending) { queued = true; return; }
  pending = true;
  try {
    const date = new Date(Date.now() + offsetDays * 86400000);
    document.getElementById("solar-date").textContent = fmtDate(date.toISOString());
    const data = await api("solar-system/positions", { date: date.toISOString() });
    for (const p of [...data.planets, ...data.small_bodies]) {
      const b = bodies.get(p.name);
      if (!b) continue;
      b.pos = p;
      b.mesh.position.copy(toScene(p.pos));
    }
    if (selectedName) renderCard(selectedName);
  } catch (err) {
    console.error(err);
  } finally {
    pending = false;
    if (queued) { queued = false; refresh(); }
  }
}

function renderList() {
  const list = document.getElementById("solar-list");
  const groups = [["planete", "Planètes"], ["comete", "Comètes"], ["interstellaire", "Interstellaires"], ["asteroide", "Astéroïdes"]];
  list.innerHTML = groups.map(([kind, title]) => {
    const items = [...bodies.values()].filter((b) => b.info.kind === kind);
    return `<li class="dim" style="cursor:default">${title}</li>` + items.map((b) =>
      `<li data-name="${esc(b.info.name)}"><span>${esc(shortName(b.info.name))}</span></li>`).join("");
  }).join("");
  list.onclick = (e) => {
    const li = e.target.closest("li[data-name]");
    if (li) focus(li.dataset.name);
  };
}

function focus(name) {
  const b = bodies.get(name);
  if (!b) return;
  selectedName = name;
  const target = b.mesh.position.clone();
  controls.target.copy(target);
  camera.position.copy(target.clone().add(new THREE.Vector3(6, 8, 12)));
  for (const [n, o] of bodies) o.line.material.opacity = n === name ? 1 : (o.info.kind === "planete" ? 0.25 : 0.12);
  renderCard(name);
}

function pick(e) {
  const rect = renderer.domElement.getBoundingClientRect();
  const mouse = new THREE.Vector2(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
  const ray = new THREE.Raycaster();
  ray.setFromCamera(mouse, camera);
  // tolérance : on prend l'objet dont la projection à l'écran est la plus proche du clic
  let best = null, bestD = 0.04;
  for (const [name, b] of bodies) {
    const p = b.mesh.position.clone().project(camera);
    const d = Math.hypot(p.x - mouse.x, p.y - mouse.y);
    if (p.z < 1 && d < bestD) { best = name; bestD = d; }
  }
  if (best) focus(best);
}

function renderCard(name) {
  const b = bodies.get(name);
  const card = document.getElementById("body-card");
  const i = b.info, p = b.pos ?? {};
  card.classList.remove("hidden");
  const el = i.elements;
  card.innerHTML = `
    <button class="card-close" aria-label="Fermer">×</button>
    <h2>${esc(shortName(i.name))}</h2>
    <span class="tag">${esc(i.kind === "planete" ? "Planète" : TYPE_LABELS[i.kind])}</span>
    ${i.note ? `<p class="note">${esc(i.note)}</p>` : ""}
    <dl class="kv">
      <dt>Distance au Soleil</dt><dd>${fmtNum(p.sun_au, 3)} UA</dd>
      <dt>Distance à la Terre</dt><dd>${fmtNum(p.earth_au, 3)} UA</dd>
      <dt>soit</dt><dd>${fmtNum((p.earth_au ?? 0) * 149.6, 1)} M km</dd>
      ${i.kind === "planete" ? `
        <dt>Rayon</dt><dd>${fmtNum(i.radius_km)} km</dd>
        <dt>Année</dt><dd>${fmtNum(i.period_days, 1)} jours</dd>` : `
        <dt>Excentricité</dt><dd>${fmtNum(el.e, 4)}${el.e >= 1 ? " (orbite ouverte)" : ""}</dd>
        <dt>Périhélie (q)</dt><dd>${fmtNum(el.q, 3)} UA</dd>
        <dt>Inclinaison</dt><dd>${fmtNum(el.i, 1)}°</dd>
        <dt>Période</dt><dd>${i.period_years ? `${fmtNum(i.period_years, 1)} ans` : "ne revient jamais"}</dd>
        <dt>Dernier périhélie</dt><dd>${fmtDate(p.last_perihelion)}</dd>
        <dt>Prochain périhélie</dt><dd>${fmtDate(p.next_perihelion)}</dd>`}
    </dl>
    ${i.kind !== "planete" ? `<p class="small dim">${esc(i.name)} · ${esc(i.orbit_class ?? "")}<br>Éléments orbitaux : JPL Small-Body Database.</p>` : ""}`;
  card.querySelector(".card-close").onclick = () => { card.classList.add("hidden"); selectedName = null; };
}

function setOffset(days) {
  offsetDays = Math.max(-36500, Math.min(36500, Math.round(days)));
  document.getElementById("solar-range").value = offsetDays;
  refresh();
}

function bindControls() {
  document.getElementById("solar-range").addEventListener("input", (e) => setOffset(+e.target.value));
  for (const b of document.querySelectorAll("#view-solar [data-step]")) b.addEventListener("click", () => setOffset(offsetDays + +b.dataset.step));
  document.getElementById("solar-today").addEventListener("click", () => setOffset(0));
  const play = document.getElementById("solar-play");
  play.addEventListener("click", () => {
    if (playing) { clearInterval(playing); playing = null; play.textContent = "▶"; return; }
    play.textContent = "⏸";
    playing = setInterval(() => setOffset(offsetDays + 4), 80);
  });
  document.getElementById("solar-compress").addEventListener("change", (e) => {
    compressed = e.target.checked;
    build();
    refresh();
    if (selectedName) focus(selectedName);
  });
}
