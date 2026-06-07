"""Lokale, offline Spracherkennung — Ersatz für LocalTranscriptionService.swift.

Statt WhisperKit/CoreML (nur Apple) nutzen wir **faster-whisper** (CTranslate2),
das auf jedem Linux-Rechner läuft. Die Modelle werden bei Bedarf von Hugging Face
geladen und in ~/.local/share/blitztext/models/ zwischengespeichert.

Wir bieten dieselben drei Stufen wie das Original an:
    "small"          -> Whisper Small (empfohlen, schnell)        [Standard]
    "large-v3"       -> Whisper Large v3 (genau, langsam)
    "large-v3-turbo" -> Whisper Large v3 Turbo (genau & schneller)
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from .settings_store import MODELS_DIR

RECOMMENDED_FAST_MODEL_NAME = "small"

# Modell-Steckbriefe: interner Name -> (HF-Repo, Anzeigename, Kurzname).
_MODELS: dict[str, dict[str, str]] = {
    "small": {
        "repo": "Systran/faster-whisper-small",
        "display": "Whisper Small",
        "short": "Whisper Small",
    },
    "large-v3": {
        "repo": "Systran/faster-whisper-large-v3",
        "display": "Whisper Large v3",
        "short": "Whisper Large",
    },
    "large-v3-turbo": {
        "repo": "deepdml/faster-whisper-large-v3-turbo-ct2",
        "display": "Whisper Large v3 Turbo",
        "short": "Whisper Turbo",
    },
}

# Reihenfolge im Auswahlmenü (empfohlenes Modell zuerst) — wie supportedModelNames im Original.
SUPPORTED_MODEL_NAMES = ["small", "large-v3", "large-v3-turbo"]


class LocalTranscriptionError(Exception):
    """Fehler bei der lokalen Transkription (deutsch, nutzerlesbar)."""


# MARK: - Namen & Anzeige -----------------------------------------------------


def normalized_model_name(name: str) -> str:
    name = (name or "").strip()
    return name if name in _MODELS else RECOMMENDED_FAST_MODEL_NAME


def display_name(name: str) -> str:
    return _MODELS.get(normalized_model_name(name), {}).get("display", name)


def short_display_name(name: str) -> str:
    return _MODELS.get(normalized_model_name(name), {}).get("short", name)


def _repo(name: str) -> str:
    return _MODELS[normalized_model_name(name)]["repo"]


def model_page_url(name: str) -> str:
    return f"https://huggingface.co/{_repo(name)}"


# MARK: - Installations-Status ------------------------------------------------


def _cache_dir_for(name: str) -> Path:
    """Ordner, in dem Hugging Face das Modell ablegt (innerhalb unseres Modell-Ordners)."""
    repo = _repo(name)
    return MODELS_DIR / ("models--" + repo.replace("/", "--"))


def is_model_installed(name: str) -> bool:
    """True, wenn das Modell bereits heruntergeladen wurde (model.bin vorhanden)."""
    cache_dir = _cache_dir_for(name)
    if not cache_dir.is_dir():
        return False
    # HF legt die Dateien unter snapshots/<hash>/ ab — wir suchen eine model.bin.
    return any(cache_dir.glob("snapshots/*/model.bin"))


def installed_models() -> list[str]:
    return [n for n in SUPPORTED_MODEL_NAMES if is_model_installed(n)]


def model_options() -> list[str]:
    """Alle wählbaren Modelle in Anzeige-Reihenfolge (wie modelOptions() im Original)."""
    return list(SUPPORTED_MODEL_NAMES)


def resolved_model_name(preferred: str) -> str:
    """Bevorzugtes Modell, falls installiert; sonst irgendein installiertes; sonst das bevorzugte."""
    name = normalized_model_name(preferred)
    if is_model_installed(name):
        return name
    others = installed_models()
    return others[0] if others else name


# MARK: - Modell laden & transkribieren ---------------------------------------

# Zwischenspeicher für das geladene Modell (Laden dauert, daher nur einmal).
_loaded_model = None
_loaded_model_name: str | None = None
_lock = threading.Lock()


def _get_model(name: str):
    """Lädt das faster-whisper-Modell (oder gibt das bereits geladene zurück)."""
    global _loaded_model, _loaded_model_name
    from faster_whisper import WhisperModel  # Lazy-Import (großes Paket)

    name = normalized_model_name(name)
    with _lock:
        if _loaded_model is not None and _loaded_model_name == name:
            return _loaded_model

        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        # CPU + int8: läuft auf jedem Rechner ohne spezielle Grafikkarte.
        model = WhisperModel(
            _repo(name),
            device="cpu",
            compute_type="int8",
            download_root=str(MODELS_DIR),
        )
        _loaded_model = model
        _loaded_model_name = name
        return model


def prepare(name: str) -> None:
    """Lädt das Modell vorab in den Speicher (für schnelleren ersten Einsatz)."""
    _get_model(name)


def download_and_install(name: str, status_handler: Callable[[str], None] | None = None) -> None:
    """Lädt das Modell herunter (falls noch nicht vorhanden) und in den Speicher.

    faster-whisper lädt beim ersten Erstellen automatisch von Hugging Face herunter.
    Einen Prozent-Fortschritt liefert es leider nicht — wir melden daher nur Status-Texte."""
    if status_handler:
        status_handler("Modell wird geladen ...")
    _get_model(name)
    if status_handler:
        status_handler(f"{display_name(name)} ist installiert.")


def transcribe(audio_path: Path, language: str, model_name: str) -> str:
    resolved_language = (language or "").strip() or None
    model = _get_model(resolved_model_name(model_name))

    segments, _info = model.transcribe(str(audio_path), language=resolved_language)
    text = " ".join(segment.text for segment in segments).strip()

    if not text:
        raise LocalTranscriptionError("Das lokale Modell hat keinen Text erkannt.")
    return text
