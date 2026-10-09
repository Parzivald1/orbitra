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
