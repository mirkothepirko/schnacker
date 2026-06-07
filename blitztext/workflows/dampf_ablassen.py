"""Blitztext $%&! (Frust entschärfen) — portiert aus DampfAblassenWorkflow.swift.

Zwei Phasen: Whisper-Transkription, dann GPT formuliert die Nachricht ruhig um.
"""

from __future__ import annotations

from pathlib import Path

from ..models import DampfAblassenSettings, PhaseState, WorkflowType
from ..services import llm
from ..services import transcription as remote
from .base import Workflow


class DampfAblassenWorkflow(Workflow):
    def __init__(self, settings: DampfAblassenSettings, custom_terms: list[str] | None = None,
                 language: str = "de") -> None:
        super().__init__(WorkflowType.DAMPF_ABLASSEN, language=language, custom_terms=custom_terms)
        self.settings = settings

    def _process(self, audio_path: Path, duration: float, vocabulary_hints: list[str]) -> str:
        # Phase 1: Transkription
        self._set_phase(PhaseState.running("Wird transkribiert ..."))
        raw_text = remote.transcribe(audio_path, custom_terms=vocabulary_hints, language=self.language)
        cleaned_raw = self._reject_if_artifact(raw_text, duration)
        self._check_cancelled()

        # Phase 2: GPT formuliert um
        self._set_phase(PhaseState.running("Wird umformuliert ..."))
        answer = llm.dampf_ablassen(cleaned_raw, self.settings.system_prompt)
        if answer.strip() == "KEINE_AUFNAHME_ERKANNT":
            raise RuntimeError("Keine Aufnahme erkannt.")
        return answer
