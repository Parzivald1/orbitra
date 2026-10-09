// Module « Ciel ce soir » : Lune, planètes visibles, passages de l'ISS.
import { icons, moonSvg } from "./icons.js";
import { api, esc, fmtNum, fmtDateTime, fmtTime, fmtDate, loading, failed, countdownEl, refreshCountdowns } from "./util.js";

let el;

export async function init(state) { el = document.getElementById("sky-content"); await render(state); }
export const onLocation = render;

async function render(state) {
  const { lat, lon, alt, name } = state.location;
  loading(el, "Lecture du ciel…");
  try {
    const [sky, iss] = await Promise.all([
      api("sky", { lat, lon, alt }),
      api("satellites/25544/passes", { lat, lon, alt, hours: 96 }).catch(() => null),
    ]);
    const visible = sky.planets.filter((p) => p.visible_tonight).sort((a, b) => a.magnitude - b.magnitude);
    const hidden = sky.planets.filter((p) => !p.visible_tonight);
    const issVisible = iss?.passes.filter((p) => p.visible) ?? [];

    el.innerHTML = `
      <div class="page-title"><h1>Ciel ce soir</h1><span class="dim">${icons.pin(14)} ${esc(name)} · ${fmtDate(new Date().toISOString())}</span></div>
      <div class="grid">
        <div class="tile">
          <h3>Soleil</h3>
          <div class="row"><span class="big">${fmtTime(sky.sun.set)}</span><span class="dim">coucher</span></div>
          <p class="small dim">Observation possible de ${fmtTime(sky.sun.night_start)} à ${fmtTime(sky.sun.night_end)} (Soleil à plus de 6° sous l'horizon) · lever ${fmtTime(sky.sun.rise)}</p>
        </div>
        <div class="tile">
          <h3>Lune</h3>
          <div class="row"><span class="moon-disc">${moonSvg(sky.moon.angle)}</span>
            <div><div class="big" style="font-size:1.3rem">${esc(sky.moon.name)}</div>
            <div class="small dim">éclairée à ${fmtNum(sky.moon.illumination * 100)} %</div></div></div>
          <div class="bar moon" style="margin:.6rem 0"><span style="width:${sky.moon.illumination * 100}%"></span></div>
          <p class="small dim">Lever ${fmtTime(sky.moon.rise)} · coucher ${fmtTime(sky.moon.set)}<br>
          ${sky.moon.next_quarters.map((q) => `${esc(q.name)} : ${fmtDate(q.date)}`).join("<br>")}</p>
        </div>
        <div class="tile">
          <h3>Station spatiale (ISS)</h3>
          ${issVisible.length ? `
            <div class="small dim">Prochain passage visible à l'œil nu</div>
            <div class="big" style="font-size:1.3rem">${esc(fmtDateTime(issVisible[0].rise))}</div>
            ${countdownEl(issVisible[0].rise, "maintenant !")}
            <p class="small dim">Apparaît au ${esc(issVisible[0].rise_dir)}, culmine à ${issVisible[0].max_elevation}° au ${esc(issVisible[0].max_dir)}, disparaît au ${esc(issVisible[0].set_dir)}.</p>`
            : `<p class="small dim">Pas de passage visible à l'œil nu dans les 4 prochains jours (l'ISS doit être éclairée pendant que vous êtes dans la nuit).</p>`}
        </div>
      </div>

      <div class="tile" style="margin-top:1rem">
        <h3>Planètes visibles cette nuit</h3>
        ${visible.length ? visible.map(planetRow).join("") : `<p class="dim">Aucune planète bien placée cette nuit.</p>`}
        ${hidden.length ? `<p class="small dim" style="margin-top:.8rem">Trop proches du Soleil ou sous l'horizon : ${hidden.map((p) => esc(p.name)).join(", ")}.</p>` : ""}
      </div>
      <p class="small dim">Magnitude : plus le chiffre est petit, plus l'astre est brillant (Vénus ≈ −4, limite à l'œil nu ≈ +6). Uranus et Neptune demandent des jumelles ou un télescope.</p>`;
    refreshCountdowns();
  } catch (err) { failed(el, err); }
}

function planetRow(p) {
  const eye = p.magnitude <= 5.5 ? `${icons.eye(14)} œil nu` : `${icons.scope(14)} jumelles / télescope`;
  return `<div class="planet-row">
    <strong>${esc(p.name)}</strong>
    <span class="small">${esc(p.constellation)}</span>
    <span class="small">au mieux vers ${fmtTime(p.best_time)} (${p.best_altitude}°)</span>
    <span class="small dim">mag ${fmtNum(p.magnitude, 1)} · ${eye}</span>
  </div>`;
}
