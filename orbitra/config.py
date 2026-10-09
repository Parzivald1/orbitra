"""Réglages globaux d'Orbitra."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
DATA_DIR = Path(__file__).resolve().parent / "data"
CACHE_DIR = ROOT / ".cache"

# Position par défaut : Observatoire de Paris (modifiable depuis l'interface)
DEFAULT_LAT = 48.8361
DEFAULT_LON = 2.3364
DEFAULT_ALT_M = 400.0

USER_AGENT = "Orbitra/0.1 (projet etudiant ; https://github.com/Parzivald1/orbitra)"
