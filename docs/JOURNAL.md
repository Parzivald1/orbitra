# Journal de bord

[English version](JOURNAL.en.md)

Je note ici ce que je fais, ce qui casse et comment je le répare. Au début c'était pour moi, pour ne pas refaire
deux fois les mêmes erreurs. Maintenant je me dis que c'est aussi le meilleur moyen de montrer comment je travaille.

---

## Jour 1 : la v0.1

### Le point de départ

Au départ je voulais juste savoir où était l'ISS. Puis je me suis dit : pourquoi s'arrêter là ? Les satellites,
les débris, les éclipses, les comètes, les étoiles filantes, les lancements… J'ai découpé tout ça en six modules
indépendants pour pouvoir finir chaque morceau avant de passer au suivant, sinon je savais que j'allais tout
commencer et rien finir.

### Les choix techniques, et pourquoi

Python avec FastAPI pour le serveur, parce que je connais Python et que FastAPI génère la documentation de l'API tout
seul. Pour l'interface, du JavaScript sans framework : pas de Node, pas de compilation, on ouvre et ça marche.
CesiumJS pour le globe (c'est ce qu'utilisent des pros pour ce genre de visualisation) et Three.js pour le système
solaire, plus léger.

Le choix le plus important : calculer la position des 18 000 satellites **dans le navigateur** et pas sur le serveur.
Le serveur envoie les données une fois, et c'est le navigateur de chaque utilisateur qui fait les calculs. Sinon,
avec plusieurs utilisateurs, le serveur aurait explosé.

Et j'ai voulu coder moi-même les calculs importants (Kepler, changements de repère, passages au-dessus de chez soi)
au lieu d'appeler une bibliothèque qui fait tout. C'est plus long, mais c'est le seul moyen de vraiment comprendre,
et ça se teste.

### Ce qui a marché du premier coup

Sept routes de l'API sur neuf, et les 41 premiers tests. Quand j'ai vu le catalogue s'afficher avec 18 621 objets,
dont 10 658 Starlink et 2 680 débris, ça m'a fait un choc : je savais qu'il y en avait beaucoup, mais pas à ce point.

### Ce qui a cassé

**CelesTrak m'a bloqué.** En testant les adresses plusieurs fois, le site a fini par me répondre « GP data has not
updated since your last successful download ». Leurs données ne changent que toutes les 2 h et ils refusent qu'on
les retélécharge avant. Logique, ils sont financés par des dons. J'ai ajouté un cache sur disque : on ne redemande
jamais un groupe avant 2 h, et si CelesTrak refuse, on garde la dernière copie.

**« Ciel ce soir » plantait avec une erreur 500.** Je passais `+1` et `-1` à la fonction de lever et coucher, alors
qu'elle attend `Direction.Rise` et `Direction.Set`. Une vraie erreur bête, mais ça m'a appris à lire la doc avant.

**Les éclipses plantaient à cause d'un `NaN`.** Pour une éclipse partielle, l'ombre de la Lune ne touche pas la Terre,
donc il n'y a pas de « point central » et la bibliothèque renvoie `NaN`, que le format JSON refuse. Maintenant on
n'envoie ce point que s'il existe, et un test vérifie qu'aucun `NaN` ne sort.

**Les « dernières » exoplanètes dataient de 2022.** J'ai mis du temps à comprendre : l'archive de la NASA applique
le `TOP 30` avant le `ORDER BY`. Donc elle prenait 30 planètes au hasard, puis les triait. Je récupère maintenant
les découvertes des deux dernières années et je trie moi-même.

**Le globe était tout noir dans mes captures automatiques.** Les satellites apparaissaient mais pas la Terre. J'ai
écrit une page de test : Cesium disait que la Terre était bien chargée. En vérifiant dans un vrai Chrome, tout
s'affichait. Le problème venait de Chrome en mode sans fenêtre, pas de mon code. Leçon retenue : vérifier son outil
de test avant d'accuser son code.

**Il manquait la comète de Halley.** Il manquait en fait 8 objets sur 22. J'envoyais 22 requêtes en même temps au
JPL, qui en refusait une partie, et mon cache gardait l'échec pendant 24 h. Double erreur. Correctif : 4 requêtes
maximum en parallèle, 3 essais, et une erreur n'est jamais mise en cache.

**Mercure était « visible » en plein crépuscule.** Et Jupiter était « au mieux » à 7 h 57, après le lever du Soleil.
Ma fenêtre de nuit allait du coucher au lever du Soleil, alors qu'on ne voit rien tant que le Soleil n'est pas à
au moins 6° sous l'horizon. Corrigé, et une planète doit maintenant monter à 10° minimum.

**Cinq codes de sites de lancement étaient faux.** Je les avais écrits de mémoire. Erreur. J'ai repris la liste
officielle de CelesTrak (42 sites). Depuis je vérifie systématiquement à la source.

### Côté sécurité

Je fais du pentest à côté, donc je ne pouvais pas laisser passer ça. Tout texte qui vient d'une API externe est
échappé avant d'être affiché (sinon un titre d'article piégé pourrait exécuter du code : faille XSS). Les liens ne
peuvent être qu'en http ou https. Le numéro de satellite est vérifié avant d'entrer dans la requête envoyée à
Wikidata (anti-injection). Les coordonnées GPS sont validées côté serveur. Et aucune clé secrète dans le code.

---

## Jour 1, la suite : la v0.2

J'ai montré la première version et j'ai eu des retours (surtout les miens, en fait) : la Terre était pixelisée,
on ne voyait rien quand on zoomait, les satellites étaient des points sans intérêt, et je voulais voir de vraies
images de l'espace. Pas des simulations.

### La Terre pixelisée

Deux causes. La texture de base de Cesium est une petite image basse résolution, et sur un écran Retina, Cesium
dessine par défaut à **la moitié de la résolution** de l'écran pour économiser. J'ai branché une imagerie satellite
haute résolution (on voit les toits de Paris), forcé la vraie résolution et ajouté l'anticrénelage.

### Le vrai satellite en 3D

La NASA publie des modèles 3D de ses satellites. J'en ai trouvé 22 qui correspondent à des satellites encore en
orbite, et j'ai vérifié chaque numéro de satellite dans le catalogue avant de les associer.

Les modèles sont d'abord sortis **tout noirs**. Le rendu réaliste de Cesium n'a pas de lumière ambiante dans
l'espace, donc la face non éclairée est noire. J'ai écrit un petit *shader* (un programme qui tourne sur la carte
graphique) pour les éclairer correctement.

Ensuite l'ISS est sortie **toute blanche**. J'ai ouvert le fichier : le modèle de la NASA n'a aucune couleur,
ses 19 matériaux sont gris. J'ai donc identifié les pièces par leur forme. Les panneaux solaires, par exemple,
sont le grand élément plat de 30 × 45 m avec très peu de sommets. Puis j'ai écrit un script (`tools/recolor_glb.py`)
qui change uniquement les couleurs dans le fichier, sans toucher à la géométrie. C'est le bug qui m'a le plus plu à résoudre.

### Les autres bugs du globe

- Une **icône jaune restait collée sur l'ISS** en vue rapprochée. C'étaient les autres modules de la station
  (Nauka, etc.), catalogués à part. Et au démarrage, leurs positions n'étaient pas encore calculées quand je
  cherchais les voisins de l'ISS. Je calcule maintenant leurs positions au moment de la sélection.
- **Des bandes sur la Terre** quand on suivait l'ISS. J'ai désactivé les effets un par un pour trouver le coupable :
  c'est l'éclairage jour/nuit de Cesium près de la frontière jour/nuit. Il s'efface maintenant sous 6 500 km.
- **18 000 petits dessins de satellites**, ça piquait les yeux. Ils sont devenus des points lumineux doux, et le
  détail est réservé au satellite choisi.
- **La caméra partait toute seule au-dessus de la France** à cause d'un recentrage déclenché au mauvais moment.

### Les vraies caméras

Je me suis fixé une règle : **aucune image de synthèse présentée comme réelle**. La vue 3D du globe est écrite
« reconstitution ». Les caméras, elles, sont de vraies images avec leur vraie date : photos de l'équipage de l'ISS,
Terre entière toutes les 10 minutes (GOES), Soleil (SDO, SOHO), Terre vue depuis 1,5 million de km (DSCOVR).

Petite surprise : le flux « temps réel » de la sonde SDO datait de 18 jours. L'appli affiche donc l'âge de chaque
image et ne dit « temps réel » que si elle a moins de 6 heures.

### La galerie, le plus dur

Je voulais une galerie qui garde seulement les photos où on voit vraiment bien une planète ou la Lune.

La première version filtrait sur le texte des titres. Résultat : elle a gardé une photo d'arbre (« Apollo 14 Moon
Tree », un arbre planté avec des graines qui étaient allées autour de la Lune), un lever de Lune sur une ville,
une colline appelée « Mars Hill », des cartes, un enregistrement sonore et des doublons. Pas terrible.

Pour la deuxième version, j'ai fait analyser **l'image elle-même** : les bords doivent être noirs (fond spatial),
il doit y avoir une seule grosse zone claire (un seul astre, pas un montage), d'une taille raisonnable, à peu près
ronde, et nette (variance du laplacien). Je l'ai calibrée sur de vraies images avant de l'activer. Résultat :
49 vrais portraits sur 197 images analysées. Jupiter par Hubble, la Lune par Galileo, Uranus par Voyager 2.

### La caméra embarquée de l'ISS

Les dernières photos des astronautes s'affichent, et j'ai découvert en les parcourant que la Française
**Sophie Adenot** est à bord en ce moment.

J'ai aussi préparé un « film du trajet » : les astronautes prennent souvent des rafales (une photo par seconde),
et mises bout à bout elles montrent exactement ce qu'ils ont vu. Mais la base qui donne l'heure et la position de
chaque photo demande une clé gratuite de la NASA, que j'ai demandée. En attendant, le regroupement des photos est
testé avec des données factices. Je préfère le dire clairement : cette partie n'a pas encore tourné avec de vraies données.

---

## Jour 1, encore : l'OSINT

Je fais du pentest, donc l'OSINT (le renseignement en sources ouvertes), ça me parle. Pour les satellites, les
grands outils d'OSINT ne servent à rien : ils sont faits pour enquêter sur des sites ou des personnes. Les vraies
sources, ce sont des bases de données ouvertes.

- **GCAT**, de Jonathan McDowell (astrophysicien au Harvard-Smithsonian) : la base la plus complète qui existe,
  69 433 objets. Constructeur, masse, dimensions, programme, et surtout la classe d'utilisateur : civil,
  commercial, **militaire** ou amateur. On y trouve aussi l'enregistrement du satellite à l'ONU.
- **SatNOGS**, un projet open source de stations radio amateurs : les fréquences de chaque satellite. Pour l'ISS il y
  a 50 émetteurs, dont ceux des scaphandres russes, qu'on peut écouter avec une clé SDR à 30 €.

Je voulais aussi utiliser la base UCS, mais elle n'est plus accessible à son ancienne adresse.

Un petit bug trouvé par les tests : « Cylindre +  2 panneaux » avec un double espace. Ce genre de détail, c'est
exactement pour ça que j'écris des tests.

---

## Jour 1, toujours : enfin la pollution vue de l'espace

C'était l'idée de départ du projet, et c'est probablement la partie la plus scientifique.

Un satellite ne « voit » pas un gaz. Il mesure la lumière du Soleil renvoyée par la Terre, et chaque molécule absorbe
des longueurs d'onde bien précises. Plus il y a de NO₂ entre le sol et le satellite, plus ses raies d'absorption
sont marquées. Sentinel-5P fait ça pour toute la planète chaque jour avec son instrument TROPOMI.

La NASA republie ces mesures sous forme de tuiles colorées (GIBS). J'ai branché six couches : NO₂ et SO₂ (Sentinel-5P),
monoxyde de carbone et méthane (Aqua), particules fines (MODIS) et couche d'ozone (Suomi NPP).

**Lire la vraie valeur sous la souris.** Une image colorée, c'est joli mais ce n'est pas une mesure. La NASA publie
pour chaque couche la table qui associe chaque couleur à un intervalle de valeurs. Je calcule donc dans quelle tuile
et quel pixel tombe le point cliqué (projection Web Mercator), je lis sa couleur et je la convertis en valeur.
Résultat : Shanghai à 1,5 × 10¹⁶ molécules/cm² de NO₂, le Pacifique à 1,6 × 10¹⁴, l'Etna qui ressort en SO₂.

**Trois « pas de mesure » d'affilée.** Paris, Shanghai, le Pacifique : rien. J'ai d'abord cru à un bug dans mon calcul
de pixel. En regardant les tuiles, le calcul était juste : ce jour-là, les nuages ne laissaient que 16 % de la tuile
de Paris exploitable. Maintenant, si le pixel est vide, je cherche la mesure la plus proche (jusqu'à 15 km), puis
je remonte jusqu'à 7 jours en arrière, et l'appli dit d'où vient le chiffre.

**Une carte mouchetée illisible.** Une seule journée de mesures, c'est plein de trous et de bruit. Les scientifiques
ne publient jamais ça, ils font des moyennes. Mon serveur fait donc pareil : il décode les tuiles des 7 derniers jours
en valeurs, fait la moyenne pixel par pixel en ignorant les trous, puis recolore avec la même table. Et pour ne pas
noyer la Terre sous un voile jaune, tout ce qui est sous le niveau de fond devient transparent : seules les zones
vraiment polluées se colorent.

Un petit bug au passage : certaines tables de couleurs donnent une valeur unique au lieu d'un intervalle,
ce qui faisait planter la lecture des particules fines.

Une limite honnête : au-dessus du Sahara, MODIS ne mesure pas les aérosols (le sable est trop clair et l'éblouit).
