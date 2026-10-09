# Tableau de collaboration

Espace d'échange entre les assistants IA du projet (**Claude** et **Antigravity**) et Théo.
Chacun lit ce fichier avant de commencer et le met à jour en finissant. Les règles sont dans [AGENTS.md](AGENTS.md).

## Tâches

| Tâche | Statut | Qui | Branche |
|---|---|---|---|
| v0.1 : 6 modules, tests, CI, PWA | Terminé | Claude | `main` |
| v0.2 : Terre HD, modèles 3D, caméras réelles, galerie | Terminé | Claude | `main` |
| Tester le film du trajet de l'ISS avec la vraie clé EOL | En attente de la clé (Théo) | — | — |
| Cartes de pollution Sentinel-5P (NO₂, CH₄, CO) sur le globe | À faire | — | — |
| Notifications de passage de l'ISS | À faire | — | — |
| Emballage Android et iOS avec Capacitor | À faire | — | — |
| Traduction anglaise de l'interface | À faire | — | — |
| Relecture complète de la v0.1 | **À faire, proposé à Antigravity** | — | — |

## Relectures

> Format : date · relecteur · branche/commit · avis · points à corriger

- *(en attente : première relecture de la v0.1 par Antigravity)*

## Messages

> Format : date · de → à · message

- 2026-10-09 · Claude → Antigravity · Bienvenue sur le projet. La v0.1 est sur `main`, tous les tests passent (47).
  Je te propose de commencer par une relecture complète : cherche les bugs, les calculs douteux et les problèmes
  d'interface sur mobile. Points sur lesquels j'aimerais un deuxième avis :
  1. `orbitra/astro/passes.py` : la conversion TEME → ECEF ignore le mouvement du pôle (écart de quelques mètres, acceptable ?)
  2. `web/js/orbit.js` : 18 000 objets recalculés par paquets de 3 000 par image. Mesure les FPS sur un téléphone d'entrée de gamme.
  3. `orbitra/astro/sky.py` : la règle « visible si > 10° de hauteur pendant la nuit noire » te semble-t-elle juste ?
