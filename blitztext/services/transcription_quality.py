"""Qualitätsprüfung der Aufnahme — 1:1 portiert aus TranscriptionQualityService.swift.

Diese Regeln verhindern, dass aus winzigen Aufnahmen (versehentliches Antippen)
sinnlose Whisper-"Halluzinationen" als Text durchrutschen.
"""

from __future__ import annotations

import unicodedata

# Mindestlänge einer Aufnahme in Sekunden. Kürzere werden verworfen.
MINIMUM_RECORDING_DURATION = 0.3


def should_reject_recording(duration: float) -> bool:
    """True, wenn die Aufnahme zu kurz war, um sie überhaupt zu verschicken."""
    return duration < MINIMUM_RECORDING_DURATION


def cleaned_transcript(text: str) -> str:
    """Entfernt führende/abschließende Leerzeichen und Zeilenumbrüche."""
    return text.strip()


def _is_letter(ch: str) -> bool:
    """Zählt ein Zeichen als Buchstabe? (entspricht CharacterSet.letters)."""
    return unicodedata.category(ch).startswith("L")


def is_likely_artifact(text: str, recording_duration: float) -> bool:
    """Erkennt typische Whisper-Artefakte bei sehr kurzen Aufnahmen.

    Regeln exakt wie im Original:
    - leer oder ohne Buchstaben -> Artefakt
    - < 0.55 s und (>= 5 Wörter oder >= 32 Zeichen) -> Artefakt
    - < 0.8 s und >= 56 Zeichen -> Artefakt
    """
    cleaned = cleaned_transcript(text)
    if not cleaned:
        return True

    words = cleaned.split()
    letters = sum(1 for ch in cleaned if _is_letter(ch))

    if letters == 0:
        return True

    if recording_duration < 0.55 and (len(words) >= 5 or len(cleaned) >= 32):
        return True

    if recording_duration < 0.8 and len(cleaned) >= 56:
        return True

    return False
