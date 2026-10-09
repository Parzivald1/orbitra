// Module « Découvertes » : dernières exoplanètes confirmées + actualité spatiale.
import { api, esc, safeUrl, fmtNum, fmtDate, loading, failed } from "./util.js";

let el;

export async function init() {
  el = document.getElementById("discoveries-content");
  loading(el, "Chargement des découvertes…");
  try {
    const [exo, news] = await Promise.all([api("exoplanets"), api("news").catch(() => [])]);
    el.innerHTML = `
      <div class="page-title"><h1>Découvertes</h1></div>
      <div class="grid">
        <div class="tile"><h3>Exoplanètes confirmées</h3><div class="big">${fmtNum(exo.total)}</div>
          <p class="small dim">Des planètes en orbite autour d'autres étoiles que le Soleil. La première autour d'une étoile comme la nôtre date de 1995 (51 Pegasi b).</p></div>
      </div>

      <h2 style="margin-top:1.5rem">Les plus récentes</h2>
      <div class="tile table-wrap"><table>
        <thead><tr><th>Planète</th><th>Publiée</th><th>Méthode</th><th>Instrument</th><th>Rayon (Terre = 1)</th><th>Année (jours)</th><th>Distance</th></tr></thead>
        <tbody>${exo.latest.map((p) => `<tr>
          <td><strong>${esc(p.pl_name)}</strong></td>
          <td>${esc(p.disc_pubdate ?? p.disc_year)}</td>
          <td class="small">${esc(p.method_fr)}</td>
          <td class="small">${esc(p.disc_facility)}</td>
          <td class="num">${fmtNum(p.pl_rade, 2)}</td>
          <td class="num">${fmtNum(p.pl_orbper, 2)}</td>
          <td class="num">${p.sy_dist ? `${fmtNum(p.sy_dist * 3.2616)} al` : "—"}</td></tr>`).join("")}</tbody>
      </table></div>
      <p class="small dim">Source : NASA Exoplanet Archive. al = années-lumière.</p>

      <h2 style="margin-top:1.5rem">Actualité spatiale</h2>
      <div class="grid wide">${news.map((a) => `
        <a class="tile" href="${esc(safeUrl(a.url))}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;color:inherit">
          ${a.image_url ? `<img class="muted-img" src="${esc(safeUrl(a.image_url))}" alt="" loading="lazy" referrerpolicy="no-referrer">` : ""}
          <strong>${esc(a.title)}</strong>
          <p class="small dim">${esc(a.news_site)} · ${fmtDate(a.published_at)}</p>
          <p class="small">${esc((a.summary ?? "").slice(0, 220))}${(a.summary ?? "").length > 220 ? "…" : ""}</p>
        </a>`).join("")}</div>
      <p class="small dim">Articles en anglais · source : Spaceflight News API.</p>`;
  } catch (err) { failed(el, err); }
}
