"""Die drei Workflows mit zweitem Schritt — Lektorat, Platt und Basel.

Alle drei laufen identisch ab:

    1. Aufnahme transkribieren (OpenAI Whisper)
    2. den Text von einem Chat-Modell umschreiben lassen

Unterschiedlich sind nur der Statustext in Schritt 2 und die aufgerufene
LLM-Funktion. Deshalb gibt es hier **eine** Klasse und eine Tabelle mit den drei
Steckbriefen, statt drei fast gleicher Dateien.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..models import (
    DampfAblassenSettings,
    EmojiTextSettings,
    Phase,
    PhaseState,
    TextImprovementSettings,
    WorkflowType,
)
from ..services import llm
from ..services import transcription as remote
from .base import Workflow

# Signalwort: Antwortet das Modell damit, hat es keinen echten Text erkannt.
_NO_AUDIO_MARKER = "KEINE_AUFNAHME_ERKANNT"


class LLMWorkflow(Workflow):
    """Transkribieren, dann umschreiben.

    `rewrite` bekommt den transkribierten Text und gibt den fertigen zurück.
    `status_text` ist die Meldung, die während des Umschreibens angezeigt wird.
    """

    def __init__(self, workflow_type: WorkflowType, status_text: str,
                 rewrite: Callable[[str], str], language: str = "de",
                 custom_terms: list[str] | None = None) -> None:
        super().__init__(workflow_type, language=language, custom_terms=custom_terms)
        self.status_text = status_text
        self.rewrite = rewrite

    def _process(self, audio_path: Path, duration: float, vocabulary_hints: list[str]) -> str:
        # Phase 1: Transkription
        self._set_phase(PhaseState(Phase.RUNNING, "Wird transkribiert ..."))
        raw_text = remote.transcribe(audio_path, custom_terms=vocabulary_hints,
                                     language=self.language)
        cleaned_raw = self._reject_if_artifact(raw_text, duration)
        self._check_cancelled()

        # Phase 2: Umschreiben durch das Chat-Modell
        self._set_phase(PhaseState(Phase.RUNNING, self.status_text))
        answer = self.rewrite(cleaned_raw)
        if answer.strip() == _NO_AUDIO_MARKER:
            raise RuntimeError("Keine Aufnahme erkannt.")
        return answer


# MARK: - Die drei Steckbriefe ------------------------------------------------


def text_improvement(settings: TextImprovementSettings, language: str = "de") -> LLMWorkflow:
    """Lektorat. Eigennamen kommen aus diesen Einstellungen."""
    return LLMWorkflow(
        WorkflowType.TEXT_IMPROVER,
        status_text="Text wird verbessert ...",
        rewrite=lambda text: llm.improve(text, settings),
        language=language,
        custom_terms=settings.custom_terms,
    )


def dampf_ablassen(settings: DampfAblassenSettings, custom_terms: list[str] | None = None,
                   language: str = "de") -> LLMWorkflow:
    """Platt — Hochdeutsch nach Plattdeutsch."""
    return LLMWorkflow(
        WorkflowType.DAMPF_ABLASSEN,
        status_text="Wird ins Platt übersetzt ...",
        rewrite=lambda text: llm.dampf_ablassen(text, settings.system_prompt),
        language=language,
        custom_terms=custom_terms,
    )


def basel_deutsch(settings: EmojiTextSettings, custom_terms: list[str] | None = None,
                  language: str = "de") -> LLMWorkflow:
    """Basel — Hochdeutsch nach Baseldütsch.

    (Interner Name bleibt "emojiText", damit Tastenkürzel/Einstellungen stabil bleiben.)
    """
    return LLMWorkflow(
        WorkflowType.EMOJI_TEXT,
        status_text="Wird ins Baseldütsch übersetzt ...",
        rewrite=lambda text: llm.basel_deutsch(text, settings.system_prompt),
        language=language,
        custom_terms=custom_terms,
    )
