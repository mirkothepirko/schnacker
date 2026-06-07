"""Speicherorte & Einstellungen-Persistenz — Ersatz für AppSupportPaths.swift
und die Speicher-Logik aus AppState.swift.

Unter Linux gelten andere Standard-Ordner als auf dem Mac:
    Einstellungen:  ~/.config/blitztext/settings.json
    lokale Modelle: ~/.local/share/blitztext/models/

Wir lesen jeden Wert "tolerant" ein: fehlt ein Feld (z.B. nach einem Update),
nehmen wir den Standardwert — genau wie Swifts `decodeIfPresent ?? default`.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from ..models import (
    AppSettings,
    DampfAblassenSettings,
    EmojiDensity,
    EmojiTextSettings,
    HotkeyMode,
    RECOMMENDED_FAST_MODEL_NAME,
    TextImprovementSettings,
    TextTone,
    TranscriptionSettings,
)


# MARK: - Verzeichnisse -------------------------------------------------------


def _xdg_dir(env_var: str, default: Path) -> Path:
    """Gibt den XDG-Ordner zurück (Linux-Standard für Konfig/Daten)."""
    value = os.environ.get(env_var)
    return Path(value) if value else default


CONFIG_DIR = _xdg_dir("XDG_CONFIG_HOME", Path.home() / ".config") / "blitztext"
DATA_DIR = _xdg_dir("XDG_DATA_HOME", Path.home() / ".local" / "share") / "blitztext"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
MODELS_DIR = DATA_DIR / "models"


def ensure_directories() -> None:
    """Legt die Ordner an, falls sie noch nicht existieren."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)


# MARK: - Zusammengefasste Einstellungen --------------------------------------


class SettingsBundle:
    """Hält alle Einstellungs-Gruppen zusammen — wie SettingsContainer im Original."""

    def __init__(self) -> None:
        self.app = AppSettings()
        self.transcription = TranscriptionSettings()
        self.text_improvement = TextImprovementSettings()
        self.dampf_ablassen = DampfAblassenSettings()
        self.emoji_text = EmojiTextSettings()


# MARK: - Laden ---------------------------------------------------------------


def load() -> SettingsBundle:
    bundle = SettingsBundle()
    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return bundle  # Datei fehlt oder kaputt -> Standardwerte

    if not isinstance(raw, dict):
        return bundle

    bundle.app = _load_app(raw.get("app") or {})
    bundle.transcription = _load_transcription(raw.get("transcription") or {})
    bundle.text_improvement = _load_text_improvement(raw.get("textImprovement") or {})
    bundle.dampf_ablassen = _load_dampf_ablassen(raw.get("dampfAblassen") or {})
    bundle.emoji_text = _load_emoji_text(raw.get("emojiText") or {})
    return bundle


def _enum_or_default(enum_cls, value, default):
    """Wandelt einen gespeicherten Text in einen Enum-Wert; bei Unbekanntem -> Default."""
    try:
        return enum_cls(value)
    except (ValueError, KeyError):
        return default


def _load_app(d: dict) -> AppSettings:
    return AppSettings(
        hotkey_mode=_enum_or_default(HotkeyMode, d.get("hotkeyMode"), HotkeyMode.HOLD),
        has_seen_onboarding=bool(d.get("hasSeenOnboarding", False)),
        secure_local_mode_enabled=bool(d.get("secureLocalModeEnabled", False)),
        selected_local_transcription_model_name=str(
            d.get("selectedLocalTranscriptionModelName", RECOMMENDED_FAST_MODEL_NAME)
        ),
        has_auto_selected_fast_local_model=bool(d.get("hasAutoSelectedFastLocalModel", False)),
    )


def _load_transcription(d: dict) -> TranscriptionSettings:
    return TranscriptionSettings(language=str(d.get("language", "de")))


def _load_text_improvement(d: dict) -> TextImprovementSettings:
    terms = d.get("customTerms", [])
    return TextImprovementSettings(
        system_prompt=str(d.get("systemPrompt", "")),
        custom_terms=[str(t) for t in terms] if isinstance(terms, list) else [],
        context=str(d.get("context", "")),
        tone=_enum_or_default(TextTone, d.get("tone"), TextTone.NEUTRAL),
        custom_name=str(d.get("customName", "")),
    )


def _load_dampf_ablassen(d: dict) -> DampfAblassenSettings:
    defaults = DampfAblassenSettings()
    return DampfAblassenSettings(
        system_prompt=str(d.get("systemPrompt", defaults.system_prompt)),
        custom_name=str(d.get("customName", "")),
    )


def _load_emoji_text(d: dict) -> EmojiTextSettings:
    return EmojiTextSettings(
        emoji_density=_enum_or_default(EmojiDensity, d.get("emojiDensity"), EmojiDensity.MITTEL),
        custom_name=str(d.get("customName", "")),
    )


# MARK: - Speichern -----------------------------------------------------------


def _enum_value(v):
    """Hilfsfunktion: Enum -> sein Text-Wert, alles andere unverändert."""
    return v.value if hasattr(v, "value") else v


def save(bundle: SettingsBundle) -> None:
    """Schreibt alle Einstellungen als JSON. Schlüsselnamen wie im Original (camelCase)."""
    ensure_directories()
    data = {
        "app": {
            "hotkeyMode": bundle.app.hotkey_mode.value,
            "hasSeenOnboarding": bundle.app.has_seen_onboarding,
            "secureLocalModeEnabled": bundle.app.secure_local_mode_enabled,
            "selectedLocalTranscriptionModelName": bundle.app.selected_local_transcription_model_name,
            "hasAutoSelectedFastLocalModel": bundle.app.has_auto_selected_fast_local_model,
        },
        "transcription": {"language": bundle.transcription.language},
        "textImprovement": {
            "systemPrompt": bundle.text_improvement.system_prompt,
            "customTerms": list(bundle.text_improvement.custom_terms),
            "context": bundle.text_improvement.context,
            "tone": bundle.text_improvement.tone.value,
            "customName": bundle.text_improvement.custom_name,
        },
        "dampfAblassen": {
            "systemPrompt": bundle.dampf_ablassen.system_prompt,
            "customName": bundle.dampf_ablassen.custom_name,
        },
        "emojiText": {
            "emojiDensity": bundle.emoji_text.emoji_density.value,
            "customName": bundle.emoji_text.custom_name,
        },
    }
    # Erst in eine temporäre Datei schreiben, dann umbenennen -> kein halb-geschriebener Stand.
    tmp = SETTINGS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SETTINGS_PATH)
