# Journal de bord

Ici je note tout : ce qui a marché, ce qui a planté et comment je l'ai corrigé.
C'est aussi ce qui sert à reprendre le projet (seul, avec un contributeur ou avec une IA) sans tout redécouvrir.

---

## 9 octobre 2026 : v0.1, première version complète

### L'idée de départ

Au début je voulais juste suivre l'ISS. Puis je me suis dit : pourquoi pas **tout** ce qui est dans l'espace ?
Les satellites, les débris, les éclipses, les comètes, les étoiles filantes, les lancements, les découvertes.
J'ai découpé ça en 6 modules indépendants pour pouvoir les finir un par un.

### Choix techniques

| Choix | Pourquoi |
|---|---|
| **Python + FastAPI** pour le backend | Je connais Python, FastAPI génère tout seul la doc de l'API (`/docs`) |
| **JavaScript sans framework** pour le front | Pas besoin de Node ni de build : on ouvre et ça marche |
| **CesiumJS** pour le globe | Globe 3D pro, gère le jour et la nuit et des milliers de points |
| **Three.js** pour le système solaire | Plus léger que Cesium pour une simple scène 3D |
| **Calcul des positions dans le navigateur** | 18 000 satellites à recalculer en continu : impossible côté serveur pour plusieurs utilisateurs. Le serveur envoie les TLE une fois, le navigateur fait SGP4. |
| **Mes propres calculs** (Kepler, changements de repère, passages) | Pour comprendre la physique au lieu d'appeler une boîte noire, et pouvoir les tester |

### Ce qui a marché du premier coup

- 7 routes de l'API sur 9 au premier lancement
- Les 41 premiers tests (Kepler, passages, éclipses) sont passés directement
- Le catalogue complet : **18 621 objets**, dont 10 658 Starlink et 2 680 débris

### Ce qui n'a PAS marché, et les correctifs

**1. CelesTrak m'a bloqué**
En testant les URL plusieurs fois, CelesTrak a répondu : *« GP data has not updated since your last successful download »*.
Leurs données ne changent que toutes les 2 h, et ils refusent qu'on les retélécharge avant.
→ **Correctif** : cache sur disque (`.cache/*.tle`). On ne redemande jamais un groupe avant 2 h, et si CelesTrak
refuse ou tombe en panne, on garde la dernière copie. Prévu aussi : si le gros groupe « active » n'est pas dispo,
on reconstruit le catalogue à partir des petits groupes.

**2. « Ciel ce soir » plantait (erreur 500)**
J'avais passé `+1` et `-1` à la fonction de lever et coucher d'Astronomy Engine, qui attend `Direction.Rise` / `Direction.Set`.
→ **Correctif** : utiliser l'énumération `Direction`.

**3. Les éclipses plantaient : `NaN` dans le JSON**
Pour une éclipse partielle, le cône d'ombre de la Lune ne touche pas la Terre : il n'y a pas de « point central »
et la bibliothèque renvoie `NaN`, que le JSON refuse.
→ **Correctif** : on n'envoie la latitude et la longitude que si elles existent. Un test vérifie qu'aucun `NaN` ne sort.

**4. Les « dernières » exoplanètes dataient de 2022**
L'archive de la NASA applique `TOP 30` **avant** le `ORDER BY` : le tri ne servait à rien.
→ **Correctif** : je récupère les découvertes des 2 dernières années et je trie en Python.

**5. Le globe apparaissait tout noir dans les captures automatiques**
Les satellites s'affichaient mais pas la Terre. J'ai écrit une page de diagnostic : Cesium disait que la Terre était
bien chargée (`tilesLoaded=true`). En testant dans un vrai Chrome piloté par le protocole DevTools, tout s'affichait.
→ **Conclusion** : un défaut du Chrome « headless » (sans fenêtre), pas de mon code. Leçon : vérifier l'outil de test avant d'accuser le code.

**6. Il manquait 8 comètes et astéroïdes sur 22 (dont Halley !)**
J'envoyais 22 requêtes en même temps au JPL, qui en refusait une partie. Pire : mon cache gardait l'échec en mémoire pendant **24 h**.
→ **Correctif** : 4 requêtes maximum en parallèle (sémaphore), 3 essais avec une attente qui augmente,
et une erreur n'est **jamais** mise en cache. Résultat : 22/22.

**7. Mercure « visible » en plein jour**
L'appli disait que Mercure était visible au coucher du Soleil à 5° de hauteur, et que Jupiter était
« au mieux » à 7 h 57… après le lever du Soleil.
→ **Correctif** : la fenêtre d'observation va maintenant du moment où le Soleil passe 6° sous l'horizon jusqu'à l'aube,
et une planète doit monter à au moins 10°.

**8. Des codes de sites de lancement faux**
J'avais écrit de mémoire la liste des codes (PKMTR, TSC, TNSTA…) : 5 étaient faux, et Sentinel-5P apparaissait
lancé depuis « PLMSC » sans traduction.
→ **Correctif** : liste officielle reprise depuis celestrak.org/satcat/launchsites.php (42 sites).
Leçon : toujours vérifier à la source.

**9. `qlmanage` (aperçu macOS) bloqué en générant les icônes PNG**
→ **Correctif** : petit script Python qui dessine l'icône pixel par pixel et écrit le PNG à la main (zlib + CRC).

### Améliorations demandées en cours de route

- **Plus d'émojis** : ils s'affichent différemment selon les téléphones. Remplacés par des icônes SVG au trait,
  et la Lune est dessinée en SVG selon sa vraie phase.
- **Fiche complète quand on clique sur un satellite** : sa mission, ce qu'il récolte, depuis quand, d'où il est parti,
  le pays, la fin de mission, une photo. Trois sources croisées : CelesTrak SATCAT (tous les objets), Wikidata et Wikipédia
  (objets connus), et des fiches que j'ai rédigées par famille (Starlink, GPS, Galileo, Sentinel, NOAA…).

### Sécurité (déformation pentest oblige)

- Tout texte venant d'une API externe est échappé avant affichage (anti-XSS), et les liens sont filtrés (http/https seulement)
- Le numéro NORAD est vérifié (chiffres uniquement) avant d'être mis dans la requête SPARQL de Wikidata (anti-injection)
- Coordonnées GPS validées côté serveur (latitude entre −90 et 90, etc.)
- Aucune clé d'API dans le code

### Prochaine étape

Les cartes de pollution mesurées par Sentinel-5P (NO₂, CH₄, CO) affichées sur le globe : l'idée de départ du projet.

---

## 9 octobre 2026 (suite) : v0.2, Terre HD, vrais satellites en 3D, vraies caméras

### Ce que j'ai demandé

- Une Terre vraiment belle, pas pixelisée, où on peut zoomer jusqu'aux rues comme sur Maps
- Des satellites plus lisibles, et le **vrai** satellite quand on s'approche
- Accéder à la caméra des satellites, mais **seulement de vraies images, pas de simulation**
- Des caméras qui filment l'espace, et une galerie qui garde les clichés où on voit vraiment bien une planète ou la Lune
- Une caméra embarquée de l'ISS avec les photos des astronautes, et un « film » de son trajet fait de vraies photos

### Ce qui a été fait

| Demande | Solution |
|---|---|
| Terre HD | Imagerie satellite Esri (jusqu'au niveau 19 : rues et toits) + rendu à la vraie résolution de l'écran (Retina) + anticrénelage |
| Satellites lisibles | Points lumineux doux par catégorie ; en vue rapprochée, tous les autres disparaissent |
| Le vrai satellite | Modèles 3D officiels de la NASA pour 22 satellites (ISS, Hubble, Terra, Aqua, Landsat, GOES…) ; sinon sa vraie photo |
| Caméras des satellites | Direct vidéo de l'ISS ; images du jour de Terra, Aqua, Suomi NPP, NOAA-20/21 (NASA GIBS) ; photo de la Terre entière toutes les 10 min (GOES-18/19) |
| Caméras de l'espace | Soleil (SDO, SOHO), Terre depuis 1,5 million de km (DSCOVR/EPIC), avec l'heure réelle de chaque cliché |
| Galerie | Enregistrement automatique, avec une **analyse d'image** qui vérifie que l'astre est seul, entier et net |
| Caméra embarquée ISS | Dernières photos de l'équipage ; film du trajet à partir des rafales de photos (nécessite une clé NASA gratuite) |

### Ce qui n'a PAS marché, et les correctifs

**10. La Terre était floue et pixelisée**
Deux causes : la texture de base de Cesium (NaturalEarthII) est une vignette basse résolution, et sur un écran
Retina Cesium dessine par défaut à **demi-résolution**.
→ Imagerie Esri haute résolution + `useBrowserRecommendedResolution: false` + `msaaSamples: 4`.

**11. La caméra partait toute seule au-dessus de la France**
`setPov(false)` recentrait la caméra à chaque sélection, même si on n'était pas en vue satellite.
→ On ne recentre que si on sortait vraiment de cette vue.

**12. Les modèles 3D étaient tout noirs, puis tout blancs**
Noirs : le rendu physique de Cesium n'a pas de lumière ambiante dans l'espace. Correctif : un petit *shader*
(programme pour la carte graphique) qui éclaire le modèle avec le Soleil plus une lumière ambiante.
Blancs : le modèle de l'ISS publié par la NASA n'a **aucune couleur** (19 matériaux, tous gris à 40 %).
J'ai identifié les pièces par leur géométrie (les panneaux solaires sont le grand élément plat de 30 × 45 m
avec très peu de sommets) et écrit `tools/recolor_glb.py`, qui réécrit uniquement les couleurs dans le fichier `.glb`.

**13. L'icône jaune restait collée sur l'ISS en vue rapprochée**
Les autres modules de l'ISS (Nauka…) sont catalogués à part et restaient affichés. Et au démarrage, leurs
positions n'étaient pas encore calculées quand on cherchait les voisins de l'ISS.
→ On calcule leurs positions au moment de la sélection, et ils disparaissent en vue rapprochée.

**14. Des bandes sur la Terre en suivant l'ISS**
Diagnostic en désactivant les effets un par un : c'est l'éclairage jour/nuit de Cesium près du terminateur.
→ L'effet jour/nuit s'efface sous 6 500 km d'altitude. J'ai aussi ajouté le préchargement des tuiles voisines
(la caméra file à 7,6 km/s, les tuiles n'avaient pas le temps d'arriver).

**15. 18 000 petits dessins de satellites, illisible**
→ Points lumineux doux. Le détail est réservé au satellite choisi.

**16. La galerie gardait n'importe quoi**
v1 (filtre sur le texte) : un arbre planté avec des graines d'Apollo 14, un lever de Lune sur une ville, une colline
nommée « Mars Hill », des cartes, un enregistrement sonore, des doublons.
→ v2 : **analyse de l'image elle-même** (bords noirs = fond spatial, une seule zone claire = un seul astre,
taille, forme, netteté). Calibrée sur de vraies images avant de l'activer. Résultat : 49 vrais portraits sur 197 images analysées.

**17. Miniatures cassées dans la galerie**
J'avais supposé que la taille « medium » existait toujours : faux pour les anciennes images de la NASA.
→ On utilise l'aperçu réellement fourni par l'API.

### Honnêteté sur les caméras

- La « Vue 3D » du globe est une **reconstitution** et c'est écrit dessus. Ce n'est jamais présenté comme une caméra.
- Le flux « temps réel » de la sonde SDO date du 21 septembre (en panne côté NASA) : l'appli affiche l'âge réel
  de chaque image et ne dit « temps réel » que si elle a moins de 6 h.
- Le film du trajet de l'ISS n'a pas encore pu être testé avec de vraies données : il faut la clé gratuite de la NASA
  (demande à jsc-earthweb@mail.nasa.gov). Le regroupement des photos en séquences est testé avec des données factices.
