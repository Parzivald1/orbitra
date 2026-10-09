// Module « Caméras » : uniquement de vraies images, jamais de simulation.
//  - caméra embarquée de l'ISS : photos de l'équipage + film du trajet (séquences de vraies photos)
//  - caméras spatiales : Terre (GOES, DSCOVR) et Soleil (SDO, SOHO), avec l'heure réelle de chaque cliché
//  - galerie : la Lune et les planètes, seulement quand on les voit vraiment bien
import { api, esc, safeUrl, fmtDate, fmtDateTime, loading, failed, openModal as openSharedModal, closeModal } from "./util.js";
import { icons } from "./icons.js";

let el, galleryData = null, galleryFilter = "all";

export async function init() {
  el = document.getElementById("cameras-content");
  el.innerHTML = `
    <div class="page-title"><h1>Caméras</h1><span class="dim">Uniquement de vraies images, avec leur date de prise de vue</span></div>
    <section id="cam-iss"></section>
    <section id="cam-space"></section>
    <section id="cam-gallery"></section>`;
  await Promise.all([renderIss(), renderSpaceCams(), renderGallery()]);
}

// ---------- Fenêtre modale (vidéo, film, photo en grand) ----------

let stopPlayer = null;
function openModal(html) {
  openSharedModal(html, () => { stopPlayer?.(); stopPlayer = null; });
}

function openPhoto(p) {
  openModal(`
    <img class="modal-img" src="${esc(safeUrl(p.thumb))}" alt="${esc(p.title)}">
    <h2 style="margin-top:.8rem">${esc(p.title)}</h2>
    <p class="small dim">${esc(fmtDate(p.date))} · ${esc(p.credit ?? "NASA")}</p>
    ${p.description ? `<p class="note small">${esc(p.description)}</p>` : ""}
    ${p.analysis ? `<p class="small dim">Analyse de l'image : bords noirs à ${Math.round(p.analysis.dark_border * 100)} %, astre unique à ${Math.round(p.analysis.main_blob * 100)} %, netteté ${Math.round(p.analysis.sharpness)}</p>` : ""}
    <a class="btn primary" href="${esc(safeUrl(p.full))}" target="_blank" rel="noopener noreferrer">${icons.link(13)} Image originale en haute définition</a>`);
}

// ---------- ISS : caméra embarquée ----------

async function renderIss() {
  const box = document.getElementById("cam-iss");
  loading(box, "Chargement des photos de l'équipage de l'ISS…");
  let data;
  try { data = await api("iss/photos"); } catch (err) { failed(box, err); return; }
  const photos = data.photos;
  box.innerHTML = `
    <h2>Caméra embarquée de l'ISS</h2>
    <div class="row" style="margin-bottom:.8rem">
      <button class="btn primary" id="iss-live">${icons.camera(14)} Direct vidéo</button>
      <button class="btn" id="iss-film">Film du trajet (vraies photos)</button>
      <button class="btn" id="iss-globe">Voir l'ISS sur le globe</button>
    </div>
    <p class="small dim">Les dernières photos prises par les astronautes depuis la station, publiées par la NASA.</p>
    <div class="photo-grid">${photos.map((p, i) => `
      <button class="photo" data-i="${i}" title="${esc(p.title)}">
        <img src="${esc(safeUrl(p.thumb))}" alt="${esc(p.title)}" loading="lazy">
        <span class="photo-cap">${esc(p.title)}<br><span class="dim">${esc(fmtDate(p.date))}</span></span>
      </button>`).join("")}</div>`;
  box.querySelector(".photo-grid").onclick = (e) => {
    const b = e.target.closest("[data-i]");
    if (b) openPhoto({ ...photos[+b.dataset.i], credit: "NASA / équipage de l'ISS" });
  };
  document.getElementById("iss-live").onclick = () => openModal(`
    <h2>ISS : caméras extérieures en direct</h2>
    <div class="video"><iframe src="https://www.youtube.com/embed/live_stream?channel=UCLA_DiR1FfKNvjuUpBHmylQ&autoplay=1&mute=1" title="Direct de l'ISS"
      allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe></div>
    <p class="small dim">Flux en direct de la chaîne officielle de la NASA. Écran noir = la station est dans l'ombre de la Terre ou en perte de signal (ça arrive plusieurs fois par heure).</p>`);
  document.getElementById("iss-film").onclick = () => openFilm(data);
  document.getElementById("iss-globe").onclick = () => document.querySelector('#tabs [data-view="orbit"]').click();
}

// Film du trajet : une séquence de vraies photos prises à ~1 seconde d'intervalle, lue comme une vidéo
async function openFilm(data) {
  if (!data.sequences_enabled) {
    openModal(`
      <h2>Film du trajet de l'ISS</h2>
      <p class="note">Le film est fabriqué uniquement avec les vraies photos des astronautes : ils prennent souvent
      des rafales (une photo par seconde) pendant que la station avance à 7,7 km/s. Mises bout à bout, elles montrent
      exactement ce qu'ils ont vu, avec l'heure et le point survolé de chaque image.</p>
      <p class="note small">Pour l'activer, il faut une clé gratuite de la base de photos de la NASA
      (<em>Gateway to Astronaut Photography of Earth</em>) : écrire à <strong>jsc-earthweb@mail.nasa.gov</strong>
      avec pour objet « Photos Database API Key Request », puis la mettre dans la variable <code>EOL_API_KEY</code> du serveur.</p>`);
    return;
  }
  openModal(`
    <h2>Film du trajet de l'ISS</h2>
    <div class="row"><span class="small dim">Jour</span>
      <select id="film-day" class="date-input">${data.days.map((d) => `<option value="${d}">${d.slice(6)}/${d.slice(4, 6)}/${d.slice(0, 4)}</option>`).join("")}</select>
    </div>
    <div id="film-list"></div><div id="film-player"></div>`);
  const daySel = document.getElementById("film-day");
  const loadDay = async () => {
    const list = document.getElementById("film-list");
    loading(list, "Recherche des séquences de photos…");
    try {
      const res = await api("iss/sequences", { day: daySel.value });
      if (!res.sequences.length) { list.innerHTML = `<p class="small dim">Aucune séquence ce jour-là (les photos arrivent avec quelques jours de retard).</p>`; return; }
      list.innerHTML = `<div class="seq-list">${res.sequences.slice(0, 12).map((s, i) => `
        <button class="btn" data-i="${i}">${fmtDateTime(s.start)} · ${s.count} photos${s.daylight ? "" : " · de nuit"}</button>`).join("")}</div>`;
      list.onclick = (e) => { const b = e.target.closest("[data-i]"); if (b) play(res.sequences[+b.dataset.i]); };
      play(res.sequences[0]);
    } catch (err) { failed(list, err); }
  };
  daySel.onchange = loadDay;
  loadDay();
}

function play(seq) {
  stopPlayer?.();
  const box = document.getElementById("film-player");
  box.innerHTML = `
    <div class="player"><img id="film-img" alt="Photo prise depuis l'ISS"></div>
    <div class="row">
      <button class="btn primary" id="film-toggle">Pause</button>
      <input type="range" id="film-pos" min="0" max="${seq.frames.length - 1}" value="0" style="flex:1">
    </div>
    <p class="small dim mono" id="film-info"></p>
    <p class="small dim">Séquence ${esc(seq.id)} · ${seq.count} vraies photos · NASA, équipage de l'ISS</p>`;
  const img = document.getElementById("film-img"), pos = document.getElementById("film-pos"), info = document.getElementById("film-info");
  const cache = seq.frames.map((f) => { const i = new Image(); i.src = f.src; return i; }); // préchargement
  let k = 0, playing = true;
  const show = (n) => {
    k = n;
    const f = seq.frames[k];
    img.src = cache[k].src;
    pos.value = k;
    info.textContent = `${k + 1}/${seq.frames.length} · ${new Date(f.time).toISOString().slice(11, 19)} UTC · survol ${f.lat ?? "?"}°, ${f.lon ?? "?"}°`;
  };
  show(0);
  const timer = setInterval(() => { if (playing) show((k + 1) % seq.frames.length); }, 125); // 8 images/s
  stopPlayer = () => clearInterval(timer);
  document.getElementById("film-toggle").onclick = (e) => { playing = !playing; e.target.textContent = playing ? "Pause" : "Lecture"; };
  pos.oninput = () => { playing = false; document.getElementById("film-toggle").textContent = "Lecture"; show(+pos.value); };
}

// ---------- Caméras spatiales (Terre et Soleil) ----------

function age(hours) {
  if (hours == null) return "date inconnue";
  if (hours < 1) return `il y a ${Math.round(hours * 60)} min`;
  if (hours < 48) return `il y a ${Math.round(hours)} h`;
  return `il y a ${Math.round(hours / 24)} jours`;
}

async function renderSpaceCams() {
  const box = document.getElementById("cam-space");
  loading(box, "Récupération des dernières images…");
  let data;
  try { data = await api("cameras"); } catch (err) { failed(box, err); return; }
  const groups = [...new Set(data.cameras.map((c) => c.group))];
  box.innerHTML = groups.map((g) => `
    <h2 style="margin-top:1.6rem">Caméras spatiales : ${esc(g === "Terre" ? "la Terre" : "le Soleil")}</h2>
    <div class="grid wide">${data.cameras.filter((c) => c.group === g).map(camTile).join("")}</div>`).join("");
  box.onclick = (e) => {
    const t = e.target.closest("[data-cam]");
    if (!t) return;
    const c = data.cameras.find((x) => x.id === t.dataset.cam);
    openModal(`<img class="modal-img" src="${esc(safeUrl(c.image))}" alt="${esc(c.title)}">
      <h2 style="margin-top:.8rem">${esc(c.title)}</h2>
      <p class="small dim">Photo prise le ${esc(fmtDateTime(c.taken))} (${esc(age(c.age_hours))}) · ${esc(c.credit)}</p>
      <p class="note small">${esc(c.what)}</p>`);
  };
}

function camTile(c) {
  const badge = c.fresh
    ? `<span class="rating excellente">temps réel · ${esc(age(c.age_hours))}</span>`
    : `<span class="rating moyenne" title="Le flux de l'agence est en retard ou en pause">dernière image · ${esc(age(c.age_hours))}</span>`;
  return `<button class="tile cam-tile" data-cam="${esc(c.id)}">
    ${c.image ? `<img class="cam-img" src="${esc(safeUrl(c.image))}" alt="${esc(c.title)}" loading="lazy">` : ""}
    <div class="row"><strong>${esc(c.title)}</strong></div>
    <div style="margin:.35rem 0">${badge}</div>
    <p class="small dim">${esc(c.where)}</p>
    <p class="small">${esc(c.what)}</p>
  </button>`;
}

// ---------- Galerie ----------

async function renderGallery() {
  const box = document.getElementById("cam-gallery");
  loading(box, "Chargement de la galerie (première fois : analyse des images, environ 30 s)…");
  try { galleryData = await api("gallery"); } catch (err) { failed(box, err); return; }
  drawGallery();
}

function drawGallery() {
  const box = document.getElementById("cam-gallery");
  const d = galleryData;
  const items = d.items.filter((i) => galleryFilter === "all" || i.target === galleryFilter);
  box.innerHTML = `
    <h2 style="margin-top:1.6rem">Galerie : la Lune et les planètes</h2>
    <p class="small dim">Un cliché n'est enregistré que s'il passe tous ces critères (${d.checked} images déjà analysées) :</p>
    <ul class="small dim criteria">${d.criteria.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>
    <div class="chips">
      <button class="chip ${galleryFilter === "all" ? "on" : ""}" data-t="all">Tout (${d.items.length})</button>
      ${Object.entries(d.targets).map(([k, name]) => `<button class="chip ${galleryFilter === k ? "on" : ""}" data-t="${k}">${esc(name)} (${d.counts[k]})</button>`).join("")}
    </div>
    <div class="photo-grid">${items.map((p, i) => `
      <button class="photo" data-i="${i}" title="${esc(p.title)}">
        <img src="${esc(safeUrl(p.thumb))}" alt="${esc(p.title)}" loading="lazy">
        <span class="photo-cap">${esc(p.title)}</span>
      </button>`).join("")}</div>`;
  box.querySelector(".chips").onclick = (e) => { const c = e.target.closest("[data-t]"); if (c) { galleryFilter = c.dataset.t; drawGallery(); } };
  box.querySelector(".photo-grid").onclick = (e) => { const b = e.target.closest("[data-i]"); if (b) openPhoto(items[+b.dataset.i]); };
}
