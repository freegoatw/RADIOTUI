import json
import os
from pathlib import Path


FAVORITES_PATH = Path.home() / ".config" / "radio" / "favorites.json"


def _ensure_dir():
    """Crée le répertoire de config s'il n'existe pas."""
    FAVORITES_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_favorites() -> list[dict]:
    """Charge les favoris depuis le fichier JSON."""
    _ensure_dir()
    if FAVORITES_PATH.exists():
        try:
            with open(FAVORITES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_favorites(favorites: list[dict]) -> None:
    """Sauvegarde les favoris dans le fichier JSON."""
    _ensure_dir()
    with open(FAVORITES_PATH, "w", encoding="utf-8") as f:
        json.dump(favorites, f, indent=2, ensure_ascii=False)


def is_favorite(station: dict, favorites: list[dict]) -> bool:
    """Vérifie si une station est en favori (par URL)."""
    url = station.get("url") or station.get("video_url")
    return any(f.get("url") == url or f.get("video_url") == url for f in favorites)


def toggle_favorite(station: dict, favorites: list[dict]) -> list[dict]:
    """Ajoute ou retire une station des favoris."""
    url = station.get("url") or station.get("video_url")

    # Cherche l'index de la station
    idx = None
    for i, fav in enumerate(favorites):
        if fav.get("url") == url or fav.get("video_url") == url:
            idx = i
            break

    if idx is not None:
        # Retire du favori
        favorites.pop(idx)
    else:
        # Ajoute au favori
        favorites.append(station.copy())

    save_favorites(favorites)
    return favorites
