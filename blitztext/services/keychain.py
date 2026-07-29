"""Sicheres Speichern des API-Keys — Ersatz für KeychainService.swift.

Statt der macOS-Keychain nutzen wir den **GNOME-Schlüsselbund** über die
Python-Bibliothek `keyring`. Der Key wird verschlüsselt vom Betriebssystem
verwaltet und liegt NICHT im Klartext in einer Datei oder im Code.
"""

from __future__ import annotations

import keyring
import keyring.errors

# Name, unter dem unser Eintrag im Schlüsselbund liegt.
_SERVICE_NAME = "app.blitztext"
_KEY_NAME = "openai_api_key"

# Kleiner Zwischenspeicher (Cache), damit nicht bei jedem Tastendruck der
# Schlüsselbund abgefragt wird — wie `invalidateCache()` im Original.
# Der Wert `False` steht für "noch nicht gelesen" (None ist ein gültiges Ergebnis).
_cached: str | None | bool = False


def load() -> str | None:
    """Liest den gespeicherten API-Key. None, wenn keiner hinterlegt ist."""
    global _cached
    if _cached is not False:
        return _cached  # type: ignore[return-value]
    try:
        _cached = keyring.get_password(_SERVICE_NAME, _KEY_NAME)
    except keyring.errors.KeyringError:
        _cached = None
    return _cached


def save(value: str) -> None:
    """Speichert den API-Key verschlüsselt. Wirft eine Ausnahme bei Fehler."""
    global _cached
    keyring.set_password(_SERVICE_NAME, _KEY_NAME, value)
    _cached = value


def invalidate_cache() -> None:
    """Leert den Zwischenspeicher, damit beim nächsten load() neu gelesen wird."""
    global _cached
    _cached = False


def is_configured() -> bool:
    """True, wenn ein OpenAI-Key hinterlegt ist (für Online-Workflows nötig)."""
    return bool(load())
