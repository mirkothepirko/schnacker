"""Qualitätsprüfung der Aufnahme — portiert aus TranscriptionQualityService.swift.

Diese Regeln verhindern, dass aus winzigen Aufnahmen (versehentliches Antippen)
sinnlose Whisper-"Halluzinationen" als Text durchrutschen.
"""

from __future__ import annotations

# Mindestlänge einer Aufnahme in Sekunden. Kürzere werden verworfen.
MINIMUM_RECORDING_DURATION = 0.3


def is_likely_artifact(text: str, recording_duration: float) -> bool:
    """Erkennt typische Whisper-Artefakte bei sehr kurzen Aufnahmen.

    Regeln exakt wie im Original:
    - leer oder ohne Buchstaben -> Artefakt
    - < 0.55 s und (>= 5 Wörter oder >= 32 Zeichen) -> Artefakt
    - < 0.8 s und >= 56 Zeichen -> Artefakt

    `str.isalpha()` deckt dabei dieselben Unicode-Kategorien ab wie das
    CharacterSet.letters des Originals — inklusive Umlauten und ß.
    """
    cleaned = text.strip()
    if not any(ch.isalpha() for ch in cleaned):
        return True

    if recording_duration < 0.55 and (len(cleaned.split()) >= 5 or len(cleaned) >= 32):
        return True

    return recording_duration < 0.8 and len(cleaned) >= 56
