// Point d'entrée : onglets, position de l'observateur, horloge.
import { esc } from "./util.js";

const DEFAULT_LOC = { lat: 48.8361, lon: 2.3364, alt: 400, name: "Paris" };

export const state = {
  location: loadLocation(),
};

function loadLocation() {
  try {
    const saved = JSON.parse(localStorage.getItem("orbitra.location"));
    if (saved && Number.isFinite(saved.lat) && Number.isFinite(saved.lon)) return saved;
  } catch { /* stockage indisponible : on garde la valeur par défaut */ }
  return { ...DEFAULT_LOC };
}

function setLocation(loc) {
  state.location = loc;
  try { localStorage.setItem("orbitra.location", JSON.stringify(loc)); } catch { /* idem */ }
  document.getElementById("loc-name").textContent = loc.name;
  window.dispatchEvent(new CustomEvent("orbitra:location", { detail: loc }));
}

document.getElementById("loc-name").textContent = state.location.name;
document.getElementById("locate").addEventListener("click", () => {
  if (!navigator.geolocation) return alert("La géolocalisation n'est pas disponible sur cet appareil.");
  navigator.geolocation.getCurrentPosition(
    (pos) => setLocation({
      lat: +pos.coords.latitude.toFixed(4),
      lon: +pos.coords.longitude.toFixed(4),
      alt: Math.round(pos.coords.altitude ?? 200),
      name: `${pos.coords.latitude.toFixed(2)}°, ${pos.coords.longitude.toFixed(2)}°`,
    }),
    (err) => alert(`Position refusée ou indisponible (${esc(err.message)})`),
    { enableHighAccuracy: false, timeout: 10000 },
  );
});

// Horloge UTC (les astronomes travaillent en temps universel)
const clock = document.getElementById("clock");
setInterval(() => { clock.textContent = new Date().toISOString().slice(11, 19) + " UTC"; }, 1000);

// ---------- Onglets : chaque module n'est chargé qu'à sa première ouverture ----------
const modules = {
  orbit: () => import("./orbit.js"),
  solar: () => import("./solar.js"),
  sky: () => import("./sky.js"),
  cameras: () => import("./cameras.js"),
  events: () => import("./events.js"),
  launches: () => import("./launches.js"),
  discoveries: () => import("./discoveries.js"),
};
const started = new Set();

async function show(view) {
  for (const b of document.querySelectorAll("#tabs button")) b.classList.toggle("active", b.dataset.view === view);
  for (const s of document.querySelectorAll(".view")) s.classList.toggle("active", s.id === `view-${view}`);
  history.replaceState(null, "", `#${view}`);
  const mod = await modules[view]();
  if (!started.has(view)) {
    started.add(view);
    await mod.init(state);
  } else {
    mod.onShow?.(state);
  }
}

export function openView(view) { return show(view); }

document.getElementById("tabs").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-view]");
  if (btn) show(btn.dataset.view);
});

window.addEventListener("orbitra:location", async () => {
  for (const view of started) (await modules[view]()).onLocation?.(state);
});

const first = location.hash.slice(1);
show(modules[first] ? first : "orbit");

// Application installable (PWA) : le service worker garde l'interface en cache
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
