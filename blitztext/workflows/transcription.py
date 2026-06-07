"""Blitztext (Diktat) — portiert aus TranscriptionWorkflow.swift.

Nimmt auf und transkribiert — online über OpenAI Whisper oder lokal über
faster-whisper, je nach gewähltem Backend.
"""

from __future__ import annotations

from pathlib import Path

from ..models import PhaseState, RECOMMENDED_FAST_MODEL_NAME, TranscriptionBackend, WorkflowType
from ..services import transcription as remote
from .base import Workflow


class TranscriptionWorkflow(Workflow):
    def __init__(self, workflow_type: WorkflowType = WorkflowType.TRANSCRIPTION,
                 custom_terms: list[str] | None = None, language: str = "de",
                 backend: TranscriptionBackend = TranscriptionBackend.REMOTE,
                 local_model_name: str = RECOMMENDED_FAST_MODEL_NAME) -> None:
        super().__init__(workflow_type, language=language, custom_terms=custom_terms)
        self.backend = backend
        self.local_model_name = local_model_name

    def _process(self, audio_path: Path, duration: float, vocabulary_hints: list[str]) -> str:
        is_local = self.backend is TranscriptionBackend.LOCAL
        self._set_phase(PhaseState.running("Wird lokal transkribiert ..." if is_local
                                           else "Wird transkribiert ..."))

        if is_local:
            # Lazy-Import: faster-whisper nur laden, wenn der Lokal-Modus wirklich genutzt wird.
            from ..services import local_transcription as local
            text = local.transcribe(audio_path, language=self.language,
                                     model_name=self.local_model_name)
        else:
            text = remote.transcribe(audio_path, custom_terms=vocabulary_hints,
                                     language=self.language)

        return self._reject_if_artifact(text, duration)
