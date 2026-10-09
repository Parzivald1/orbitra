# AGENTS.md : règles pour les assistants IA (Claude Code, Antigravity…)

Ce fichier est lu par **toutes** les IA qui travaillent sur Orbitra. Le propriétaire du projet est **@Parzivald1** :
c'est lui qui décide. Les IA proposent, codent et se relisent entre elles.

## Le projet en bref

Appli web (PWA) qui montre tout ce qui se passe dans l'espace. Backend Python FastAPI (`orbitra/`),
frontend en JS natif sans build (`web/`), tests pytest (`tests/`). Voir `README.md` et `docs/JOURNAL.md`.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn orbitra.main:app --reload     # http://127.0.0.1:8000
.venv/bin/python -m pytest -q                   # doit rester 100 % vert
```

## Règles de code

1. **Langue** : commentaires, messages d'interface, commits et docs **en français**. Noms de variables et fonctions en anglais.
2. **Pas d'émoji** dans l'interface : icônes SVG de `web/js/icons.js`.
3. **Sécurité** : tout texte externe passe par `esc()` et toute URL par `safeUrl()` (`web/js/util.js`). Jamais de clé d'API dans le code.
4. **Sources externes** : toujours derrière `ttl_cache` (`orbitra/cache.py`). Une erreur ne doit **jamais** être mise en cache.
   Respecter les limites : CelesTrak (2 h), Launch Library (15 req/h), JPL (4 requêtes en parallèle max).
5. **Tests** : toute fonction de calcul a un test qui la compare à une valeur connue. Les tests n'appellent jamais Internet.
6. **Vérifier à la source** : pas de données écrites de mémoire (codes, dates, constantes) sans lien vers la source officielle.
7. **Frontend** : un module par onglet dans `web/js/`, chargé à la première ouverture. Pas de framework, pas de build.

## Travailler à plusieurs IA

- Une branche par tâche : `claude/<sujet>` ou `antigravity/<sujet>`. Jamais de commit direct sur `main`.
- Avant de commencer : lire `COLLAB.md`, réserver sa tâche dedans (« en cours : <agent> »).
- Avant de fusionner : l'**autre** IA relit la branche et note son avis dans `COLLAB.md` (section Relectures).
- Chaque correctif important est raconté dans `docs/JOURNAL.md` (problème → cause → correctif → leçon).
- Messages de commit : `type(module): description` en français. Types : `feat`, `fix`, `docs`, `test`, `refactor`, `chore`.
