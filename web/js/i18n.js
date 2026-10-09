// Traduction de l'interface.
//
// Principe (comme gettext) : le texte français sert de clé. Chaque fichier web/i18n/<langue>.json
// donne la traduction des textes exacts, plus des motifs pour les phrases qui contiennent des chiffres
// (« pic dans 12 j » -> « peak in 12 d »). Un observateur traduit automatiquement tout ce qui
// s'affiche, y compris les textes envoyés par le serveur. Ajouter une langue = ajouter un fichier JSON.

export const LANGUAGES = { fr: "Français", en: "English" };
const LOCALES = { fr: "fr-FR", en: "en-GB" };

function detect() {
  const fromUrl = new URLSearchParams(location.search).get("lang"); // lien partagé : ?lang=en
  if (fromUrl && LANGUAGES[fromUrl]) return fromUrl;
  try {
    const saved = localStorage.getItem("orbitra.lang");
    if (saved && LANGUAGES[saved]) return saved;
  } catch { /* stockage indisponible */ }
  const nav = (navigator.languages ?? [navigator.language ?? "fr"]).map((l) => l.slice(0, 2));
  return nav.find((l) => LANGUAGES[l]) ?? "en"; // langue inconnue : l'anglais touche le plus de monde
}

export const lang = detect();
export const locale = LOCALES[lang];

let dict = null;
let patterns = [];
let compass = null;

export async function loadLanguage() {
  document.documentElement.lang = lang;
  if (lang === "fr") return;
  try {
    const res = await fetch(`i18n/${lang}.json`);
    const data = await res.json();
    dict = new Map(Object.entries(data.exact));
    patterns = data.patterns.map(([re, rep]) => [new RegExp(re, "g"), rep]);
    compass = data.compass ?? null;
  } catch {
    dict = null; // en cas de souci, on garde le français plutôt que de tout casser
  }
}

// Traduit une chaîne (utilisé aussi directement par le code, ex. étiquettes dessinées sur le globe)
export function t(text) {
  if (!dict || !text) return text;
  const trimmed = text.trim();
  if (!trimmed) return text;
  // correctif : un texte écrit sur plusieurs lignes dans le code contient des retours à la ligne
  const norm = trimmed.replace(/\s+/g, " ");
  const exact = dict.get(norm);
  if (exact !== undefined) return text.replace(trimmed, exact);
  let out = norm;
  // phrases composées « A · B » : on traduit chaque morceau connu
  if (out.includes(" · ")) {
    const parts = out.split(" · ");
    if (parts.some((p) => dict.has(p.trim()))) out = parts.map((p) => dict.get(p.trim()) ?? p).join(" · ");
  }
  if (compass && out.includes("→")) {
    out = out.replace(/\b(N|NNE|NE|ENE|E|ESE|SE|SSE|S|SSO|SO|OSO|O|ONO|NO|NNO)\b/g, (d) => compass[d] ?? d);
  }
  for (const [re, rep] of patterns) {
    re.lastIndex = 0;
    if (!re.test(out)) continue;
    re.lastIndex = 0;
    out = out.replace(re, (...m) => rep
      .replace(/\$(\d)/g, (_, i) => m[+i] ?? "")
      .replace("{body}", dict.get(m[1]) ?? m[1]));
  }
  return out === norm ? text : text.replace(trimmed, out);
}

// ---------- Traduction automatique de la page ----------

const done = new WeakMap(); // nœud -> dernière valeur traduite (évite de retraduire en boucle)
const ATTRS = ["placeholder", "title", "alt", "aria-label"];

function translateNode(node) {
  if (node.nodeType === Node.TEXT_NODE) {
    const p = node.parentElement;
    if (!p || p.closest("script,style,[data-no-i18n]")) return;
    if (done.get(node) === node.nodeValue) return;
    const out = t(node.nodeValue);
    if (out !== node.nodeValue) node.nodeValue = out;
    done.set(node, node.nodeValue);
    return;
  }
  if (node.nodeType !== Node.ELEMENT_NODE || node.closest("[data-no-i18n]")) return;
  for (const el of [node, ...node.querySelectorAll("*")]) {
    for (const a of ATTRS) {
      const v = el.getAttribute?.(a);
      if (v) { const out = t(v); if (out !== v) el.setAttribute(a, out); }
    }
  }
  const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walker.nextNode())) translateNode(n);
}

export function startAutoTranslate() {
  if (!dict) return;
  translateNode(document.body);
  if (lang === "en") document.title = "Orbitra — everything happening above our heads";
  new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.type === "characterData") translateNode(m.target);
      else if (m.type === "attributes") translateNode(m.target);
      else m.addedNodes.forEach(translateNode);
    }
  }).observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
}

export function setLanguage(code) {
  try { localStorage.setItem("orbitra.lang", code); } catch { /* idem */ }
  location.reload();
}
