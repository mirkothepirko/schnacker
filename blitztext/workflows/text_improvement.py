"""Blitztext+ (Text verbessern) — portiert aus TextImprovementWorkflow.swift.

Zwei Phasen: erst Whisper-Transkription, dann GPT-Lektorat.
"""

from __future__ import annotations

from pathlib import Path

from ..models import PhaseState, TextImprovementSettings, WorkflowType
from ..services import llm
from ..services import transcription as remote
from .base import Workflow


class TextImprovementWorkflow(Workflow):
    def __init__(self, settings: TextImprovementSettings, language: str = "de") -> None:
        super().__init__(WorkflowType.TEXT_IMPROVER, language=language,
                         custom_terms=settings.custom_terms)
        self.settings = settings

    def _process(self, audio_path: Path, duration: float, vocabulary_hints: list[str]) -> str:
        # Phase 1: Transkription
        self._set_phase(PhaseState.running("Wird transkribiert ..."))
        raw_text = remote.transcribe(audio_path, custom_terms=vocabulary_hints, language=self.language)
        cleaned_raw = self._reject_if_artifact(raw_text, duration)
        self._check_cancelled()

        # Phase 2: GPT-Verbesserung
        self._set_phase(PhaseState.running("Text wird verbessert ..."))
        return llm.improve(cleaned_raw, self.settings)
