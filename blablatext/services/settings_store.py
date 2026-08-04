"""Speicherorte & Einstellungen-Persistenz — Ersatz für AppSupportPaths.swift
und die Speicher-Logik aus AppState.swift.

Unter Linux gelten andere Standard-Ordner als auf dem Mac:
    Einstellungen:  ~/.config/blablatext/settings.json
    lokale Modelle: ~/.local/share/blablatext/models/

Statt für jedes Feld eine eigene Lese-/Schreibzeile zu pflegen, laufen wir über
die Felder der dataclasses (`dataclasses.fields`) und rechnen den Python-Namen in
den JSON-Namen um: `has_seen_onboarding` <-> `hasSeenOnboarding`. Ein neues Feld
in models.py wird damit automatisch mitgespeichert.

Gelesen wird "tolerant": fehlt ein Feld (z.B. nach einem Update) oder ist es vom
falschen Typ, nehmen wir den Standardwert — wie Swifts `decodeIfPresent ?? default`.
"""

from __future__ import annotations

import json
import os
from dataclasses import fields
from enum import Enum
from pathlib import Path

from ..models import (
    AppSettings,
    DampfAblassenSettings,
    EmojiTextSettings,
    TextImprovementSettings,
    TranscriptionSettings,
)


# MARK: - Verzeichnisse -------------------------------------------------------


def _xdg_dir(env_var: str, default: Path) -> Path:
    """Gibt den XDG-Ordner zurück (Linux-Standard für Konfig/Daten)."""
    return Path(os.environ.get(env_var) or default)


CONFIG_DIR = _xdg_dir("XDG_CONFIG_HOME", Path.home() / ".config") / "blablatext"
DATA_DIR = _xdg_dir("XDG_DATA_HOME", Path.home() / ".local" / "share") / "blablatext"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
MODELS_DIR = DATA_DIR / "models"


def ensure_directories() -> None:
    """Legt die Ordner an, falls sie noch nicht existieren."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)


# Vorgängername des Pakets — die Ordner hießen bis zur Umbenennung genauso.
VORGAENGER_NAME = "blitztext"


def migriere_vorgaenger_ordner() -> list[str]:
    """Zieht Einstellungen und geladene Modelle der Vorgängerversion einmalig um.

    Ohne diesen Schritt wären nach der Umbenennung die Einstellungen weg und die
    schon geladenen Whisper-Modelle (mehrere GB) müssten neu herunterladen.
    Umbenannt wird nur, wenn der alte Ordner da ist und der neue noch nicht —
    ein vorhandener neuer Stand wird also nie überschrieben.

    Wird absichtlich nur beim App-Start aufgerufen (nicht aus load()), damit ein
    Testlauf niemals die echten Ordner des Nutzers anfasst.
    """
    umgezogen = []
    for neu in (CONFIG_DIR, DATA_DIR):
        alt = neu.with_name(VORGAENGER_NAME)
        if alt.is_dir() and not neu.exists():
            neu.parent.mkdir(parents=True, exist_ok=True)
            alt.rename(neu)
            umgezogen.append(str(neu))
    return umgezogen


# MARK: - Zusammengefasste Einstellungen --------------------------------------

# JSON-Gruppenname -> Attributname im Bundle und zugehörige dataclass.
# Diese Namen sind der Vertrag mit bereits gespeicherten settings.json-Dateien.
_GROUPS: dict[str, tuple[str, type]] = {
    "app": ("app", AppSettings),
    "transcription": ("transcription", TranscriptionSettings),
    "textImprovement": ("text_improvement", TextImprovementSettings),
    "dampfAblassen": ("dampf_ablassen", DampfAblassenSettings),
    "emojiText": ("emoji_text", EmojiTextSettings),
}


class SettingsBundle:
    """Hält alle Einstellungs-Gruppen zusammen — wie SettingsContainer im Original."""

    def __init__(self) -> None:
        for attr, cls in _GROUPS.values():
            setattr(self, attr, cls())


# MARK: - Namen umrechnen -----------------------------------------------------


def _json_key(field_name: str) -> str:
    """`has_seen_onboarding` -> `hasSeenOnboarding` (Python-Stil -> JSON-Stil)."""
    kopf, *rest = field_name.split("_")
    return kopf + "".join(teil.capitalize() for teil in rest)


# MARK: - Laden ---------------------------------------------------------------


def _coerce(wert, standard):
    """Bringt einen gelesenen JSON-Wert auf den Typ des Standardwerts.

    Passt er nicht (kaputte Datei, altes Format), gilt der Standardwert.
    """
    if isinstance(standard, Enum):
        try:
            return type(standard)(wert)
        except (ValueError, KeyError):
            return standard
    if isinstance(standard, bool):
        return bool(wert)
    if isinstance(standard, str):
        return str(wert)
    if isinstance(standard, list):
        return [str(x) for x in wert] if isinstance(wert, list) else list(standard)
    return wert


def _load_group(cls: type, daten: dict):
    """Baut eine Einstellungs-dataclass aus dem JSON-Abschnitt."""
    standards = cls()
    werte = {}
    for f in fields(cls):
        standard = getattr(standards, f.name)
        schluessel = _json_key(f.name)
        werte[f.name] = (_coerce(daten[schluessel], standard)
                         if schluessel in daten else standard)
    return cls(**werte)


def load() -> SettingsBundle:
    bundle = SettingsBundle()
    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return bundle  # Datei fehlt oder kaputt -> Standardwerte

    if not isinstance(raw, dict):
        return bundle

    for gruppe, (attr, cls) in _GROUPS.items():
        abschnitt = raw.get(gruppe)
        if isinstance(abschnitt, dict):
            setattr(bundle, attr, _load_group(cls, abschnitt))
    return bundle


# MARK: - Speichern -----------------------------------------------------------


def save(bundle: SettingsBundle) -> None:
    """Schreibt alle Einstellungen als JSON. Schlüsselnamen wie im Original (camelCase)."""
    ensure_directories()
    data = {}
    for gruppe, (attr, cls) in _GROUPS.items():
        einstellungen = getattr(bundle, attr)
        data[gruppe] = {
            _json_key(f.name): _json_value(getattr(einstellungen, f.name))
            for f in fields(cls)
        }

    # Erst in eine temporäre Datei schreiben, dann umbenennen -> kein halb-geschriebener Stand.
    tmp = SETTINGS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SETTINGS_PATH)


def _json_value(wert):
    """Enum -> sein Textwert, Liste -> Kopie, alles andere unverändert."""
    if isinstance(wert, Enum):
        return wert.value
    return list(wert) if isinstance(wert, list) else wert
