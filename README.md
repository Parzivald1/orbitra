<div align="center">

<img src="web/icons/icon-192.png" width="96" alt="Logo Orbitra">

# Orbitra

**Tout ce qui se passe au-dessus de nos têtes, en temps réel.**

Satellites · débris · éclipses · étoiles filantes · comètes · astéroïdes · lancements · exoplanètes

[![Tests](https://github.com/Parzivald1/orbitra/actions/workflows/ci.yml/badge.svg)](https://github.com/Parzivald1/orbitra/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Licence](https://img.shields.io/badge/licence-MIT-green)

![Le globe avec les 18 000 objets suivis](docs/screenshots/orbite.png)

</div>

## Le projet

Je voulais une appli qui réponde à toutes les questions que je me pose quand je regarde le ciel :
*c'est quoi ce point lumineux qui bouge ? Il sert à quoi ce satellite ? C'est quand la prochaine éclipse ?
La prochaine pluie d'étoiles filantes, ça vaut le coup avec la Lune ? Elle est où la comète de Halley en ce moment ?*

Au lieu de recopier des listes trouvées sur Internet, Orbitra **calcule** la plupart des choses lui-même
à partir des données brutes de la NASA, de l'ESA, du JPL et de CelesTrak.

## Ce que fait l'appli

| Module | Ce qu'on y trouve |
|---|---|
| **Orbite** | Globe 3D en haute définition (on zoome jusqu'aux rues) avec **plus de 18 000 objets** en orbite, position recalculée en continu. Clic sur un objet : sa mission, ce qu'il récolte, depuis quand il est là, sa fin de mission, ses passages au-dessus de chez toi. En s'approchant, on voit le **vrai satellite en 3D** (modèles officiels de la NASA). |
| **Système solaire** | Les 8 planètes, 11 comètes célèbres, 3 objets interstellaires et 8 astéroïdes en 3D. On peut avancer ou reculer dans le temps de ±100 ans pour voir les comètes revenir. |
| **Ciel ce soir** | Phase de la Lune, planètes visibles et à quelle heure, prochain passage de l'ISS visible à l'œil nu. |
| **Événements** | Éclipses de Soleil et de Lune avec compte à rebours (dont celles visibles depuis ta position), pluies d'étoiles filantes avec une note selon la gêne de la Lune, astéroïdes qui frôlent la Terre. |
| **Caméras** | **Uniquement de vraies images** : photos des astronautes de l'ISS et son direct vidéo, la Terre entière toutes les 10 minutes (GOES), le Soleil (SDO, SOHO), et une galerie de la Lune et des planètes qui ne garde que les clichés où l'astre est vraiment bien visible (analyse d'image). |
| **Lancements** | Les prochaines fusées dans le monde, avec compte à rebours. |
| **Découvertes** | Les dernières exoplanètes confirmées et l'actualité spatiale. |

<table><tr>
<td><img src="docs/screenshots/evenements.png" alt="Éclipses et étoiles filantes"></td>
<td><img src="docs/screenshots/ciel.png" alt="Ciel ce soir"></td>
</tr><tr>
<td><img src="docs/screenshots/systeme-solaire.png" alt="Système solaire en 3D"></td>
<td><img src="docs/screenshots/fiche-satellite.png" alt="Fiche d'un satellite"></td>
</tr></table>

## La science derrière

C'est la partie qui m'a le plus appris :

- **Position des satellites** : chaque satellite est décrit par un *TLE* (deux lignes de chiffres). L'algorithme **SGP4**
  transforme ces chiffres en position, en tenant compte du frottement de l'atmosphère et de l'aplatissement de la Terre.
- **Passages au-dessus de moi** : j'ai codé moi-même la chaîne de changements de repère
  (inertiel TEME → terrestre ECEF via le temps sidéral → horizon local), puis une recherche par dichotomie
  de l'instant exact où le satellite passe l'horizon. Un passage est « visible » si le satellite est éclairé
  par le Soleil pendant que l'observateur est dans la nuit (modèle d'ombre cylindrique de la Terre).
- **Comètes et astéroïdes** : résolution de l'**équation de Kepler** (méthode de Newton) pour les orbites elliptiques,
  sa version hyperbolique pour les objets interstellaires, et l'équation de Barker pour les paraboles.
- **Éclipses, Lune, planètes** : bibliothèque [Astronomy Engine](https://github.com/cosinekitty/astronomy) (modèle VSOP87).
- **Taille des astéroïdes** : estimée à partir de la magnitude absolue *H* : D = 1329 / √albédo × 10^(−H/5).

- **Galerie** : une analyse d'image maison (bords noirs, composantes connexes, netteté par laplacien) décide si on voit vraiment bien la planète.

Tout ça est vérifié par **54 tests automatiques** qui comparent les calculs à des événements réels
(éclipse totale du 12 août 2026 en Espagne, éclipse de Lune du 7 septembre 2025, retour de Halley en 2061…).

## Lancer l'appli chez soi

```bash
git clone https://github.com/Parzivald1/orbitra.git
cd orbitra
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn orbitra.main:app --reload
```

Puis ouvrir **http://127.0.0.1:8000**. La doc de l'API se trouve sur http://127.0.0.1:8000/docs.

Options (fichier `.env.example`) : `CESIUM_ION_TOKEN` pour les bâtiments en 3D, `EOL_API_KEY` pour le film du trajet de l'ISS.

Avec Docker : `docker build -t orbitra . && docker run -p 8000:8000 orbitra`

Sur téléphone, l'appli est **installable** (PWA) : « Ajouter à l'écran d'accueil » dans le navigateur.

## Architecture

```
orbitra/
├── orbitra/              # Backend Python (FastAPI)
│   ├── main.py           # Routes de l'API
│   ├── astro/            # Calculs : kepler, passages, éclipses, étoiles filantes, ciel, système solaire
│   ├── services/         # Données externes : satellites, fiches satellites, petits corps, lancements, découvertes
│   └── data/             # Calendrier des pluies d'étoiles filantes
├── web/                  # Frontend (HTML/CSS/JS sans framework)
│   └── js/               # Un module par onglet + CesiumJS (globe) + Three.js (système solaire)
├── tests/                # Tests pytest (aucun appel réseau)
└── docs/JOURNAL.md       # Journal de bord : ce qui a marché, ce qui a planté, comment j'ai corrigé
```

## Sources de données

Toutes gratuites et publiques. Merci à elles :

| Donnée | Source |
|---|---|
| Orbites des satellites et débris | [CelesTrak](https://celestrak.org) (T.S. Kelso) |
| Fiche des satellites | CelesTrak SATCAT, [Wikidata](https://www.wikidata.org), [Wikipédia](https://fr.wikipedia.org) |
| Comètes, astéroïdes, approches | [NASA/JPL Solar System Dynamics](https://ssd.jpl.nasa.gov) |
| Lancements | [The Space Devs](https://thespacedevs.com) (Launch Library 2) |
| Exoplanètes | [NASA Exoplanet Archive](https://exoplanetarchive.ipac.caltech.edu) |
| Actualité | [Spaceflight News API](https://spaceflightnewsapi.net) |
| Pluies d'étoiles filantes | Calendrier de l'[IMO](https://www.imo.net) |
| Imagerie satellite du globe | Esri World Imagery (Maxar, Earthstar Geographics) |
| Modèles 3D des satellites | [NASA 3D Resources](https://github.com/nasa/NASA-3D-Resources) |
| Images du jour des satellites | [NASA GIBS](https://www.earthdata.nasa.gov/engage/open-data-services-software/earthdata-developer-portal/gibs-api) |
| Terre en temps réel | NOAA NESDIS STAR (GOES), NASA EPIC (DSCOVR) |
| Soleil | NASA SDO, ESA/NASA SOHO |
| Photos des astronautes | NASA Image Library, [Gateway to Astronaut Photography](https://eol.jsc.nasa.gov) |

## Feuille de route

- [x] v0.1 : orbite, système solaire, ciel, événements, lancements, découvertes
- [x] v0.2 : Terre HD, satellites en 3D, vraies caméras, galerie, caméra embarquée de l'ISS
- [ ] Cartes de pollution vues par satellite (NO₂, méthane, CO₂ mesurés par Sentinel-5P) sur le globe
- [ ] Notifications : « l'ISS passe au-dessus de toi dans 10 minutes »
- [ ] Applis Android et iOS (Capacitor) sur les stores
- [ ] Version anglaise

## Contribuer

Toute aide est la bienvenue : bug, idée, correction de texte, nouvelle source de données.
Tout est expliqué dans [CONTRIBUTING.md](CONTRIBUTING.md).

## Comment je l'ai construit

Orbitra est mon projet. Je l'ai conçu et piloté avec l'aide d'assistants IA (Claude Code, et Antigravity pour les relectures croisées),
utilisés comme des binômes de programmation. Toutes les étapes, y compris les erreurs et leurs corrections,
sont racontées dans le [journal de bord](docs/JOURNAL.md).

## Licence

[MIT](LICENSE) : tu peux réutiliser, modifier et partager le code librement.

---

<div align="center">Fait par <a href="https://github.com/Parzivald1">Parzivald1</a> · Paris</div>
