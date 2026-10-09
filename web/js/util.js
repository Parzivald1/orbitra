// Petits outils partagés : appels API, dates, comptes à rebours, échappement HTML.

export async function api(path, params = {}) {
  const url = new URL(`/api/${path}`, location.origin);
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null) url.searchParams.set(k, v);
  const res = await fetch(url);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* réponse non JSON */ }
    throw new Error(detail);
  }
  return res.json();
}

// Toute donnée venant d'une API externe passe par ici avant d'être injectée dans la page
// (évite qu'un titre d'article piégé exécute du code : faille XSS).
export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export function safeUrl(url) {
  try {
    const u = new URL(url);
    return u.protocol === "https:" || u.protocol === "http:" ? u.href : "#";
  } catch { return "#"; }
}

export const fmtDateTime = (iso) => iso ? new Date(iso).toLocaleString("fr-FR", { weekday: "short", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";
export const fmtDate = (iso) => iso ? new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" }) : "—";
export const fmtTime = (iso) => iso ? new Date(iso).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }) : "—";
export const fmtNum = (n, d = 0) => n === null || n === undefined ? "—" : Number(n).toLocaleString("fr-FR", { maximumFractionDigits: d });

export function countdownText(targetMs) {
  let ms = targetMs - Date.now();
  if (ms <= 0) return null;
  const d = Math.floor(ms / 86400000); ms -= d * 86400000;
  const h = Math.floor(ms / 3600000); ms -= h * 3600000;
  const m = Math.floor(ms / 60000); ms -= m * 60000;
  const s = Math.floor(ms / 1000);
  const pad = (x) => String(x).padStart(2, "0");
  return `${d > 0 ? `J-${d} ` : ""}${pad(h)}:${pad(m)}:${pad(s)}`;
}

// Un seul minuteur pour tous les éléments <span data-countdown="ISO">
export function countdownEl(iso, doneText = "en cours") {
  return `<span class="countdown" data-countdown="${esc(iso)}" data-done="${esc(doneText)}"></span>`;
}

function tick() {
  for (const el of document.querySelectorAll("[data-countdown]")) {
    const txt = countdownText(Date.parse(el.dataset.countdown));
    el.textContent = txt ?? el.dataset.done;
    el.classList.toggle("past", !txt);
  }
}
setInterval(tick, 1000);
export const refreshCountdowns = tick;

export function loading(el, text = "Chargement…") { el.innerHTML = `<p class="loading">${esc(text)}</p>`; }
export function failed(el, err) { el.innerHTML = `<p class="error">Impossible de charger : ${esc(err.message)}</p>`; }
