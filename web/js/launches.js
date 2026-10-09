// Module « Lancements » : les prochaines fusées dans le monde.
import { api, esc, safeUrl, fmtDateTime, loading, failed, countdownEl, refreshCountdowns } from "./util.js";

let el;

export async function init() {
  el = document.getElementById("launches-content");
  loading(el, "Récupération des prochains lancements…");
  try {
    const launches = await api("launches");
    el.innerHTML = `
      <div class="page-title"><h1>Prochains lancements</h1><span class="dim">Source : The Space Devs (Launch Library 2)</span></div>
      <div class="grid wide">${launches.map(tile).join("")}</div>`;
    refreshCountdowns();
  } catch (err) { failed(el, err); }
}

const STATUS = { Go: "excellente", TBC: "moyenne", TBD: "moyenne", Success: "excellente", Hold: "faible", Failure: "faible" };

function tile(l) {
  return `<div class="tile">
    ${l.image ? `<img class="muted-img" src="${esc(safeUrl(l.image))}" alt="" loading="lazy" referrerpolicy="no-referrer">` : ""}
    <div class="row"><strong>${esc(l.name)}</strong></div>
    <div class="row" style="margin:.35rem 0">${countdownEl(l.net, "décollé / en attente")}<span class="spacer"></span>
      <span class="rating ${STATUS[l.status_abbrev] ?? "moyenne"}" title="${esc(l.status)}">${esc(l.status_abbrev ?? "?")}</span></div>
    <p class="small dim">${esc(fmtDateTime(l.net))}${l.probability ? ` · météo favorable ${l.probability} %` : ""}</p>
    <dl class="kv">
      <dt>Opérateur</dt><dd>${esc(l.provider ?? "—")}</dd>
      <dt>Fusée</dt><dd>${esc(l.rocket ?? "—")}</dd>
      <dt>Orbite visée</dt><dd>${esc(l.orbit ?? "—")}</dd>
      <dt>Site</dt><dd>${esc(l.location ?? "—")}</dd>
    </dl>
    ${l.description ? `<p class="note small">${esc(l.description)}</p>` : ""}
  </div>`;
}
