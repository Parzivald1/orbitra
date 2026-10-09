// Icônes au trait (SVG), à la place des émojis : rendu identique sur tous les appareils.
const svg = (body, size = 16) =>
  `<svg class="icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;

export const icons = {
  pin: (s) => svg('<path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>', s),
  camera: (s) => svg('<path d="M3 8h4l2-3h6l2 3h4v11H3z"/><circle cx="12" cy="13" r="3.5"/>', s),
  eye: (s) => svg('<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>', s),
  scope: (s) => svg('<path d="M4 15l12-7 2 4-12 7z"/><path d="M16 8l2-1 2 4-2 1"/><path d="M9 18l-3 4M11 17l2 5"/>', s),
  warn: (s) => svg('<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18v.5"/>', s),
  link: (s) => svg('<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>', s),
  meteor: (s) => svg('<circle cx="16" cy="8" r="3"/><path d="M13.5 10.5L4 20M11 7l-6 6M17 13l-6 6"/>', s),
};

// Disque lunaire dessiné selon l'angle de phase (0° = nouvelle lune, 180° = pleine lune)
export function moonSvg(phaseAngle, size = 56) {
  const c = size / 2, r = size / 2 - 1;
  const f = Math.cos((phaseAngle * Math.PI) / 180); // 1 = nouvelle, -1 = pleine
  const waxing = phaseAngle < 180;                  // croissante : éclairée à droite (hémisphère nord)
  const rx = Math.abs(f) * r;
  const outer = waxing ? 1 : 0;
  const inner = (f > 0) === waxing ? 0 : 1;
  const lit = `M ${c} ${c - r} A ${r} ${r} 0 0 ${outer} ${c} ${c + r} A ${rx} ${r} 0 0 ${inner} ${c} ${c - r} Z`;
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" aria-hidden="true">
    <circle cx="${c}" cy="${c}" r="${r}" fill="#1b2135"/>
    <path d="${lit}" fill="#e8e4d4"/>
    <circle cx="${c}" cy="${c}" r="${r}" fill="none" stroke="rgba(255,255,255,.15)"/></svg>`;
}
