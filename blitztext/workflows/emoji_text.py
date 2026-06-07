"""Schnacker Basel (Hochdeutsch → Baseldütsch) — basiert auf EmojiTextWorkflow.swift.

Zwei Phasen: Whisper-Transkription, dann GPT übersetzt den Text ins Baseldütsche.
(Interner Name bleibt "emojiText", damit Tastenkürzel und Einstellungen stabil bleiben.)
"""

from __future__ import annotations

from pathlib import Path

from ..models import EmojiTextSettings, PhaseState, WorkflowType
from ..services import llm
from ..services import transcription as remote
from .base import Workflow


class EmojiTextWorkflow(Workflow):
    def __init__(self, settings: EmojiTextSettings, custom_terms: list[str] | None = None,
                 language: str = "de") -> None:
        super().__init__(WorkflowType.EMOJI_TEXT, language=language, custom_terms=custom_terms)
        self.settings = settings

    def _process(self, audio_path: Path, duration: float, vocabulary_hints: list[str]) -> str:
        # Phase 1: Transkription
        self._set_phase(PhaseState.running("Wird transkribiert ..."))
        raw_text = remote.transcribe(audio_path, custom_terms=vocabulary_hints, language=self.language)
        cleaned_raw = self._reject_if_artifact(raw_text, duration)
        self._check_cancelled()

        # Phase 2: GPT übersetzt ins Baseldütsche
        self._set_phase(PhaseState.running("Wird ins Baseldütsch übersetzt ..."))
        result = llm.basel_deutsch(cleaned_raw, self.settings.system_prompt)
        if result.strip() == "KEINE_AUFNAHME_ERKANNT":
            raise RuntimeError("Keine Aufnahme erkannt.")
        return result
