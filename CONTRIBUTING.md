# Contribuer à Orbitra

Merci de vouloir aider ! Tout le monde est bienvenu, même pour une première contribution.

## Les façons d'aider

- **Signaler un bug** : ouvre une [issue](https://github.com/Parzivald1/orbitra/issues/new/choose) avec ce que tu as fait, ce que tu attendais et ce qui s'est passé.
- **Proposer une idée** : même chose, avec le modèle « Idée ».
- **Corriger ou compléter un texte** : les fiches de satellites (`orbitra/services/satinfo.py`), les comètes (`orbitra/services/smallbodies.py`), les pluies d'étoiles filantes (`orbitra/data/meteor_showers.json`).
- **Coder une fonctionnalité** : regarde les tâches « À faire » dans [COLLAB.md](COLLAB.md).

## Installer le projet

```bash
git clone https://github.com/<ton-pseudo>/orbitra.git
cd orbitra
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn orbitra.main:app --reload
```

## Proposer une modification

1. Fais un *fork* puis une branche : `git checkout -b fix/nom-du-correctif`
2. Code, puis lance les tests : `python -m pytest -q` (ils doivent tous passer)
3. Si tu ajoutes un calcul, ajoute un test qui le compare à une valeur connue (source à l'appui)
4. Commit en français : `fix(ciel): Mercure n'est plus visible en plein jour`
5. Ouvre une *Pull Request* en expliquant le pourquoi

## Règles

- Commentaires et textes de l'interface en français
- Pas d'émoji dans l'interface (icônes SVG de `web/js/icons.js`)
- Tout texte venant d'une API externe passe par `esc()` (sécurité)
- On respecte les limites des API gratuites (voir `orbitra/cache.py`)
- On reste bienveillant dans les échanges
