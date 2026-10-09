// Module « Lancements » : prochains et derniers lancements, avec un dossier OSINT complet pour chacun.
import { api, esc, safeUrl, fmtNum, fmtDate, fmtDateTime, loading, failed, countdownEl, refreshCountdowns, openModal, showOnGlobe } from "./util.js";
import { icons } from "./icons.js";
import { locale } from "./i18n.js";

let el, mode = "upcoming", list = [];

export async function init() {
  el = document.getElementById("launches-content");
  await render();
}

async function render() {
  loading(el, "Récupération des lancements…");
  try {
    list = await api("launches", { when: mode });
  } catch (err) { failed(el, err); return; }
  el.innerHTML = `
    <div class="page-title"><h1>${mode === "upcoming" ? "Prochains lancements" : "Derniers lancements"}</h1>
      <div class="chips" style="margin:0">
        <button class="chip ${mode === "upcoming" ? "on" : ""}" data-mode="upcoming">À venir</button>
        <button class="chip ${mode === "previous" ? "on" : ""}" data-mode="previous">Récents</button>
      </div></div>
    <p class="small dim">Clique sur un lancement pour son dossier complet : d'où il part, quand, où il va, qui le gère, l'équipage, la fusée, la météo et les sources.</p>
    <div class="grid wide">${list.map(tile).join("")}</div>
    <p class="small dim">Sources : The Space Devs (Launch Library 2), Open-Meteo, CelesTrak, catalogue GCAT de J. McDowell.</p>`;
  el.querySelector(".chips").onclick = (e) => { const b = e.target.closest("[data-mode]"); if (b && b.dataset.mode !== mode) { mode = b.dataset.mode; render(); } };
  el.querySelector(".grid").onclick = (e) => { const t = e.target.closest("[data-id]"); if (t) openDossier(list.find((l) => l.id === t.dataset.id)); };
  refreshCountdowns();
}

const STATUS = { Go: "excellente", TBC: "moyenne", TBD: "moyenne", Success: "excellente", Hold: "faible", Failure: "faible", "Partial Failure": "moyenne", "In Flight": "bonne" };
const status = (l) => `<span class="rating ${STATUS[l.status_abbrev] ?? "moyenne"}" title="${esc(l.status_description ?? l.status)}">${esc(l.status ?? "?")}</span>`;

function tile(l) {
  return `<button class="tile launch-tile" data-id="${esc(l.id)}">
    ${l.image ? `<img class="muted-img" src="${esc(safeUrl(l.image))}" alt="" loading="lazy" referrerpolicy="no-referrer">` : ""}
    <strong>${esc(l.name)}</strong>
    <div class="row" style="margin:.35rem 0">${mode === "upcoming" ? countdownEl(l.net, "décollé / en attente") : ""}<span class="spacer"></span>${status(l)}</div>
    <p class="small dim">${esc(fmtDateTime(l.net))}</p>
    <dl class="kv">
      <dt>Depuis</dt><dd>${esc(l.pad.location ?? "—")}</dd>
      <dt>Opérateur</dt><dd>${esc(l.provider?.name ?? "—")}</dd>
      <dt>Destination</dt><dd>${esc(l.destination ?? l.mission.orbit_fr ?? l.mission.orbit ?? "—")}</dd>
      ${l.crew.length ? `<dt>Équipage</dt><dd>${l.crew.length} astronaute${l.crew.length > 1 ? "s" : ""}</dd>` : ""}
    </dl>
  </button>`;
}

// Heure dans un fuseau donné (celui du pas de tir, ou celui de l'utilisateur)
const inZone = (iso, timeZone) => {
  try {
    return new Date(iso).toLocaleString(locale, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone, timeZoneName: "short" });
  } catch { return "—"; }
};
const kv = (rows) => `<dl class="kv">${rows.filter(([, v]) => v !== null && v !== undefined && v !== "").map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join("")}</dl>`;
const section = (title, body) => body ? `<div class="section-title">${esc(title)}</div>${body}` : "";
const statsLine = (s) => s && s.total ? `${fmtNum(s.successes)} réussis sur ${fmtNum(s.total)} (${fmtNum(s.success_rate, 1)} %)${s.streak ? ` · ${fmtNum(s.streak)} succès d'affilée` : ""}` : null;

function openDossier(l) {
  const r = l.rocket, p = l.pad, m = l.mission, a = l.provider ?? {};
  openModal(`<div class="dossier">
    ${l.image ? `<img class="dossier-img" src="${esc(safeUrl(l.image))}" alt="" referrerpolicy="no-referrer">` : ""}
    <h2>${esc(l.name)}</h2>
    <div class="row">${status(l)}${l.webcast_live ? `<span class="rating excellente">diffusion en direct</span>` : ""}<span class="spacer"></span>${countdownEl(l.net, "décollé")}</div>
    ${l.status_description ? `<p class="small dim">${esc(l.status_description)}</p>` : ""}
    ${l.hold_reason ? `<p class="note small"><strong>Report :</strong> ${esc(l.hold_reason)}</p>` : ""}
    ${l.fail_reason ? `<p class="note small"><strong>Échec :</strong> ${esc(l.fail_reason)}</p>` : ""}

    <div class="dossier-grid">
      <div>
        ${section("Quand", kv([
          ["Heure (UTC)", esc(fmtDateTime(l.net))],
          ["Heure sur place", p.timezone ? esc(inZone(l.net, p.timezone)) : null],
          ["Chez toi", esc(inZone(l.net))],
          ["Précision", l.net_precision ? esc(l.net_precision) : null],
          ["Fenêtre de tir", l.window_start && l.window_end && l.window_start !== l.window_end ? `${esc(fmtDateTime(l.window_start))} → ${esc(fmtDateTime(l.window_end))}` : null],
          ["Météo favorable", l.probability != null ? `${l.probability} %` : null],
        ]))}

        ${section("D'où elle décolle", kv([
          ["Pas de tir", esc(p.name ?? "—")],
          ["Base", esc(p.location ?? "—")],
          ["Coordonnées", p.lat != null ? `${fmtNum(p.lat, 4)}°, ${fmtNum(p.lon, 4)}°` : null],
          ["Tirs depuis ce pas", p.launches_from_pad != null ? fmtNum(p.launches_from_pad) : null],
          ["Tirs depuis la base", p.launches_from_site != null ? fmtNum(p.launches_from_site) : null],
          ["Délai depuis le tir précédent ici", l.counts.pad_turnaround ? esc(l.counts.pad_turnaround) : null],
        ]))}
        ${p.lat != null ? `<div class="row"><button class="btn" id="d-pad">${icons.pin(14)} Voir le pas de tir sur le globe</button></div>` : ""}

        ${section("Où elle va", `
          ${m.orbit_fr || m.orbit ? `<p class="note"><strong>${esc(m.orbit_fr ?? m.orbit)}</strong>${m.orbit_abbrev && m.orbit_abbrev !== "N/A" ? ` (${esc(m.orbit_abbrev)})` : ""}</p>` : ""}
          ${m.orbit_explained ? `<p class="small">${esc(m.orbit_explained)}</p>` : ""}
          ${l.destination ? `<p class="small"><strong>Destination :</strong> ${esc(l.destination)}${l.spacecraft ? ` · vaisseau ${esc(l.spacecraft)}` : ""}</p>` : ""}
          <div id="d-objects"></div>`)}

        ${section("La mission", `${m.type ? `<span class="tag">${esc(m.type)}</span>` : ""}
          ${m.description ? `<p class="note small">${esc(m.description)}</p>` : ""}
          ${m.customers.length ? `<p class="small"><strong>Pour :</strong> ${esc(m.customers.join(", "))}</p>` : ""}`)}
      </div>

      <div>
        ${l.crew.length ? section(`Équipage (${l.crew.length})`, `<ul class="crew">${l.crew.map((c) => `<li><strong>${esc(c.name)}</strong><span class="small dim">${esc([c.role, c.agency, c.nationality].filter(Boolean).join(" · "))}</span></li>`).join("")}</ul>`) : ""}

        ${section("Qui gère le lancement", `
          <div class="row">${a.logo ? `<img class="logo-sm" src="${esc(safeUrl(a.logo))}" alt="" referrerpolicy="no-referrer">` : ""}<strong>${esc(a.name ?? "—")}</strong></div>
          ${kv([
            ["Type", a.type ? esc(a.type) : null],
            ["Pays", a.country ? esc(a.country) : null],
            ["Fondée en", a.founded ? esc(a.founded) : null],
            ["Direction", a.leader ? esc(a.leader) : null],
            ["Historique", statsLine(a.stats) ? esc(statsLine(a.stats)) : null],
            ["Ce lancement est son", l.counts.agency_this_year ? `${fmtNum(l.counts.agency_this_year)}e de l'année` : null],
          ])}`)}

        ${section("La fusée", `
          <p class="note"><strong>${esc(r.name ?? "—")}</strong>${r.reusable ? ` <span class="tag">réutilisable</span>` : ""}</p>
          ${kv([
            ["Constructeur", r.manufacturer ? esc(r.manufacturer) : null],
            ["Hauteur", r.length_m ? `${fmtNum(r.length_m, 1)} m` : null],
            ["Diamètre", r.diameter_m ? `${fmtNum(r.diameter_m, 1)} m` : null],
            ["Masse au décollage", r.launch_mass_t ? `${fmtNum(r.launch_mass_t)} t` : null],
            ["Poussée au décollage", r.thrust_kn ? `${fmtNum(r.thrust_kn)} kN` : null],
            ["Charge en orbite basse", r.leo_kg ? `${fmtNum(r.leo_kg)} kg` : null],
            ["Charge vers l'orbite GTO", r.gto_kg ? `${fmtNum(r.gto_kg)} kg` : null],
            ["Premier vol", r.maiden_flight ? esc(fmtDate(r.maiden_flight)) : null],
            ["Coût d'un lancement", r.cost_usd ? `${fmtNum(r.cost_usd / 1e6)} M$` : null],
            ["Fiabilité", statsLine(r.stats) ? esc(statsLine(r.stats)) : null],
          ])}
          ${l.boosters.map((b) => `<div class="tile booster">
            <strong>Premier étage ${esc(b.serial ?? "")}</strong>${b.flight_proven ? ` <span class="tag">déjà volé</span>` : ` <span class="tag">neuf</span>`}
            <div class="small">${b.flight_number ? `${b.flight_number}e vol` : ""}${b.first_flight ? ` · premier vol le ${esc(fmtDate(b.first_flight))}` : ""}</div>
            ${b.landing ? `<div class="small dim">${b.landing.attempt ? `Atterrissage : ${esc(b.landing.type ?? "")}${b.landing.location ? ` · ${esc(b.landing.location)}` : ""}${b.landing.success === true ? " · réussi" : b.landing.success === false ? " · raté" : ""}` : "Pas de récupération (étage sacrifié)"}</div>` : ""}
          </div>`).join("")}`)}

        ${mode === "upcoming" ? section("Météo prévue au pas de tir", `<div id="d-weather"><p class="small dim">Chargement de la prévision…</p></div>`) : ""}
      </div>
    </div>

    ${section("Les sources (OSINT)", `
      ${l.updates.length ? `<ul class="updates">${l.updates.map((u) => `<li><span class="small dim">${esc(fmtDateTime(u.date))}${u.by ? ` · ${esc(u.by)}` : ""}</span><br>${esc(u.comment ?? "")}${u.source ? ` <a href="${esc(safeUrl(u.source))}" target="_blank" rel="noopener noreferrer">${icons.link(12)} source</a>` : ""}</li>`).join("")}</ul>` : `<p class="small dim">Pas de journal public pour ce lancement.</p>`}
      ${l.videos.length ? `<p class="small"><strong>Vidéos :</strong> ${l.videos.map((v) => `<a href="${esc(safeUrl(v.url))}" target="_blank" rel="noopener noreferrer">${esc(v.title || v.publisher || "vidéo")}</a>`).join(" · ")}</p>` : ""}
      ${l.links.length ? `<p class="small"><strong>Liens :</strong> ${l.links.map((v) => `<a href="${esc(safeUrl(v.url))}" target="_blank" rel="noopener noreferrer">${esc(v.title || "lien")}</a>`).join(" · ")}</p>` : ""}
      <p class="small dim">Ce lancement est la tentative orbitale n° ${fmtNum(l.counts.orbital_ever)} de l'histoire (${fmtNum(l.counts.orbital_this_year)}e cette année).</p>`)}
  </div>`);
  refreshCountdowns();
  document.getElementById("d-pad")?.addEventListener("click", () =>
    showOnGlobe("launch", { lat: p.lat, lon: p.lon, name: `${l.name}`, inclination: currentInclination }));
  if (mode === "upcoming") loadWeather(l); else loadObjects(l);
}

let currentInclination = null;

async function loadWeather(l) {
  currentInclination = null;
  const box = document.getElementById("d-weather");
  try {
    const w = await api(`launches/${encodeURIComponent(l.id)}/weather`);
    if (!w.available) { box.innerHTML = `<p class="small dim">${esc(w.reason)}</p>`; return; }
    const cls = { favorable: "excellente", "à surveiller": "moyenne", "défavorable": "faible" }[w.verdict.level];
    box.innerHTML = `
      <div class="row"><span class="rating ${cls}">${esc(w.verdict.level)}</span>${w.verdict.concerns.length ? `<span class="small dim">${esc(w.verdict.concerns.join(", "))}</span>` : ""}</div>
      ${kv([
        ["Heure prévue", esc(fmtDateTime(w.time))],
        ["Température", `${fmtNum(w.temperature_c, 1)} °C`],
        ["Vent / rafales", `${fmtNum(w.wind_kmh)} / ${fmtNum(w.gusts_kmh)} km/h`],
        ["Nuages", `${fmtNum(w.cloud_pct)} %`],
        ["Risque de pluie", `${fmtNum(w.rain_pct)} %`],
        ["Énergie orageuse (CAPE)", `${fmtNum(w.cape)} J/kg`],
      ])}
      <p class="small dim">Repères indicatifs (chaque lanceur a ses propres règles). Source : Open-Meteo.</p>`;
  } catch (err) { box.innerHTML = `<p class="small dim">Météo indisponible (${esc(err.message)}).</p>`; }
}

async function loadObjects(l) {
  currentInclination = null;
  const box = document.getElementById("d-objects");
  box.innerHTML = `<p class="small dim">Recherche des objets mis en orbite…</p>`;
  try {
    const o = await api(`launches/${encodeURIComponent(l.id)}/objects`);
    if (!o.available) { box.innerHTML = `<p class="small dim">${esc(o.reason)}</p>`; return; }
    const first = o.objects.find((x) => x.type === "Satellite" && x.inclination) ?? o.objects.find((x) => x.inclination);
    currentInclination = first?.inclination ?? null;
    box.innerHTML = `
      <p class="small"><strong>${fmtNum(o.count)} objet${o.count > 1 ? "s" : ""} mis en orbite</strong> (désignation ${esc(o.designator)})${first ? ` · orbite atteinte : ${fmtNum(first.perigee)} × ${fmtNum(first.apogee)} km, inclinée à ${fmtNum(first.inclination, 1)}°` : ""}</p>
      <div class="table-wrap"><table class="objects"><tbody>${o.objects.slice(0, 40).map((x) => `<tr>
        <td>${esc(x.name)}</td><td class="small dim">${esc(x.type)}${x.decayed ? " · retombé" : ""}</td>
        <td class="num"><button class="btn mini" data-norad="${esc(x.norad)}">${icons.eye(12)} ${esc(x.norad)}</button></td></tr>`).join("")}</tbody></table></div>
      ${o.count > 40 ? `<p class="small dim">… et ${fmtNum(o.count - 40)} autres.</p>` : ""}`;
    box.onclick = (e) => { const b = e.target.closest("[data-norad]"); if (b) showOnGlobe("select-sat", { norad: b.dataset.norad }); };
  } catch (err) { box.innerHTML = `<p class="small dim">Objets indisponibles (${esc(err.message)}).</p>`; }
}
