"""Sicheres Speichern des API-Keys — Ersatz für KeychainService.swift.

Statt der macOS-Keychain nutzen wir den **GNOME-Schlüsselbund** über die
Python-Bibliothek `keyring`. Der Key wird verschlüsselt vom Betriebssystem
verwaltet und liegt NICHT im Klartext in einer Datei oder im Code.
"""

from __future__ import annotations

from enum import Enum

import keyring
import keyring.errors

# Name, unter dem unsere Einträge im Schlüsselbund gruppiert werden.
_SERVICE_NAME = "app.blitztext"


class KeychainKey(str, Enum):
    """Welche Geheimnisse wir speichern. Aktuell nur der OpenAI-Key."""

    OPEN_AI_API_KEY = "openai_api_key"


# Kleiner Zwischenspeicher (Cache), damit nicht bei jedem Tastendruck der
# Schlüsselbund abgefragt wird — wie `invalidateCache()` im Original.
_cache: dict[str, str | None] = {}


def load(key: KeychainKey) -> str | None:
    """Liest einen gespeicherten Wert. Gibt None zurück, wenn nichts da ist."""
    if key.value in _cache:
        return _cache[key.value]
    try:
        value = keyring.get_password(_SERVICE_NAME, key.value)
    except keyring.errors.KeyringError:
        value = None
    _cache[key.value] = value
    return value


def save(key: KeychainKey, value: str) -> None:
    """Speichert einen Wert verschlüsselt. Wirft eine Ausnahme bei Fehler."""
    keyring.set_password(_SERVICE_NAME, key.value, value)
    _cache[key.value] = value


def delete(key: KeychainKey) -> None:
    """Löscht einen gespeicherten Wert (z.B. beim Aufräumen)."""
    try:
        keyring.delete_password(_SERVICE_NAME, key.value)
    except keyring.errors.PasswordDeleteError:
        pass
    _cache.pop(key.value, None)


def invalidate_cache() -> None:
    """Leert den Zwischenspeicher, damit beim nächsten load() neu gelesen wird."""
    _cache.clear()


def is_configured() -> bool:
    """True, wenn ein OpenAI-Key hinterlegt ist (für Online-Workflows nötig)."""
    value = load(KeychainKey.OPEN_AI_API_KEY)
    return bool(value)
