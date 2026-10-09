// Module « Événements » : éclipses, pluies d'étoiles filantes, astéroïdes qui frôlent la Terre.
import { icons } from "./icons.js";
import { api, esc, fmtNum, fmtDateTime, fmtDate, loading, failed, countdownEl, refreshCountdowns } from "./util.js";

let el;

export async function init(state) { el = document.getElementById("events-content"); await render(state); }
export const onLocation = render;


async function render(state) {
  const { lat, lon, alt, name } = state.location;
  loading(el, "Calcul des éclipses et des pluies d'étoiles filantes…");
  try {
    const [ecl, meteors, neos] = await Promise.all([
      api("eclipses", { lat, lon, alt }),
      api("meteors"),
      api("close-approaches").catch(() => []),
    ]);
    const nextLocal = ecl.local[0];
    el.innerHTML = `
      <div class="page-title"><h1>Événements</h1><span class="dim">Calculés en direct, pas recopiés d'une liste</span></div>

      <div class="grid wide">
        <div class="tile hero">
          <h3>Prochaine éclipse de Soleil visible depuis ${esc(name)}</h3>
          ${nextLocal ? `
            <div class="row"><span class="big">Éclipse ${esc(nextLocal.kind)}</span><span class="spacer"></span>${countdownEl(nextLocal.start)}</div>
            <p>${esc(fmtDateTime(nextLocal.peak))} · <strong>${fmtNum(nextLocal.obscuration * 100)} %</strong> du Soleil masqué, Soleil à ${nextLocal.sun_altitude}° au-dessus de l'horizon</p>
            <div class="bar"><span style="width:${nextLocal.obscuration * 100}%;background:var(--accent-2)"></span></div>
            <p class="small dim">Début ${esc(fmtDateTime(nextLocal.start))} · fin ${esc(fmtDateTime(nextLocal.end))}. ${icons.warn(13)} Jamais d'observation sans lunettes spéciales éclipse (norme ISO 12312-2).</p>` : `<p class="dim">Aucune trouvée.</p>`}
        </div>
      </div>

      <h2 style="margin-top:1.5rem">Éclipses de Soleil (partout sur Terre)</h2>
      <div class="grid">${ecl.solar.map(solarTile).join("")}</div>

      <h2 style="margin-top:1.5rem">Éclipses de Lune</h2>
      <div class="grid">${ecl.lunar.map(lunarTile).join("")}</div>

      <h2 style="margin-top:1.5rem">Pluies d'étoiles filantes</h2>
      <div class="grid wide">${meteors.map(meteorTile).join("")}</div>
      <p class="small dim">ZHR : nombre de météores par heure dans un ciel parfait avec le radiant au zénith. En pratique on en voit 2 à 3 fois moins. La Lune est le facteur décisif.</p>

      <h2 style="margin-top:1.5rem">Astéroïdes qui frôlent la Terre (60 jours)</h2>
      ${neos.length ? `<div class="tile table-wrap"><table>
        <thead><tr><th>Objet</th><th>Date (UTC)</th><th>Distance</th><th>Dist. lunaires</th><th>Vitesse</th><th>Taille estimée</th></tr></thead>
        <tbody>${neos.map((n) => `<tr>
          <td>${esc(n.name)}</td><td>${esc(n.date)}</td>
          <td class="num">${fmtNum(n.distance_km)} km</td>
          <td class="num">${fmtNum(n.distance_ld, 2)}</td>
          <td class="num">${fmtNum(n.speed_kms, 1)} km/s</td>
          <td class="num">${n.diameter_m ? `${fmtNum(n.diameter_m[0])}–${fmtNum(n.diameter_m[1])} m` : "—"}</td></tr>`).join("")}</tbody>
      </table></div>
      <p class="small dim">Source : NASA/JPL (CNEOS). 1 distance lunaire = 384 400 km. Aucun de ces objets ne menace la Terre.</p>`
        : `<p class="dim">Données JPL indisponibles pour le moment.</p>`}`;
    refreshCountdowns();
  } catch (err) { failed(el, err); }
}

function solarTile(e) {
  const where = e.latitude !== undefined ? `Maximum à ${fmtNum(e.latitude, 1)}°, ${fmtNum(e.longitude, 1)}°` : "Partielle uniquement (régions polaires)";
  return `<div class="tile">
    <div class="row"><strong>${esc(capitalize(e.kind))}</strong><span class="spacer"></span><span class="small dim">${fmtDate(e.peak)}</span></div>
    ${countdownEl(e.peak, "passée")}
    <p class="small dim">${esc(where)}</p></div>`;
}

function lunarTile(e) {
  const dur = e.duration_total_min ? `totalité ${e.duration_total_min} min` : e.duration_partial_min ? `phase partielle ${e.duration_partial_min} min` : `pénombre ${e.duration_penumbral_min} min (peu visible)`;
  return `<div class="tile">
    <div class="row"><strong>${esc(capitalize(e.kind))}</strong><span class="spacer"></span><span class="small dim">${fmtDate(e.peak)}</span></div>
    ${countdownEl(e.peak, "passée")}
    <p class="small dim">${esc(dur)}</p></div>`;
}

function meteorTile(m) {
  const status = m.active ? `<span class="rating bonne">active en ce moment</span>` : "";
  const when = m.days_to_peak <= 0 ? "pic en cours" : `pic dans ${m.days_to_peak} j`;
  return `<div class="tile">
    <div class="row"><strong>${esc(m.name)}</strong><span class="spacer"></span>${status}</div>
    <div class="row" style="margin:.4rem 0"><span class="big" style="font-size:1.3rem">${fmtDate(m.peak_date)}</span><span class="dim">${esc(when)}</span></div>
    <dl class="kv">
      <dt>Taux max (ZHR)</dt><dd>${m.zhr} / h</dd>
      <dt>Vitesse</dt><dd>${m.speed_kms} km/s</dd>
      <dt>Radiant</dt><dd>${esc(m.radiant)}</dd>
      <dt>Corps parent</dt><dd>${esc(m.parent)}</dd>
      <dt>Lune au pic</dt><dd>${fmtNum(m.moon_illumination * 100)} %</dd>
    </dl>
    <div class="row"><span class="small dim">Conditions</span><span class="spacer"></span><span class="rating ${esc(m.rating)}">${esc(m.rating)}</span></div>
  </div>`;
}

const capitalize = (s) => s.charAt(0).toUpperCase() + s.slice(1);
