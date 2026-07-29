"""Gemeinsame Basis aller Workflows — fasst die in den Swift-Workflows
mehrfach kopierte Logik zusammen (start/stop/reset, Aufnahme, Phasen).

Ablauf wie im Original:
    start()  -> Aufnahme beginnt (Phase: running "Aufnahme läuft ...")
    stop()   -> Aufnahme endet; zu kurz? -> Fehler. Sonst: verarbeiten (im Thread).
    reset()  -> alles abbrechen, Datei verwerfen, Phase = idle.

Die eigentliche Verarbeitung (Transkription, ggf. KI-Umschreibung) steckt in der
Methode `_process()`, die jeder konkrete Workflow selbst ausfüllt. `_process()`
läuft in einem Hintergrund-Thread, damit die Oberfläche flüssig bleibt.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from ..models import Phase, PhaseState, WorkflowType
from ..services import transcription_quality as quality
from ..services.audio_recorder import AudioRecorder


class WorkflowCancelled(Exception):
    """Wird intern geworfen, wenn der Workflow mittendrin abgebrochen wurde."""


class Workflow:
    """Basisklasse. Konkrete Workflows erben hiervon und überschreiben `_process`."""

    def __init__(self, workflow_type: WorkflowType, language: str = "de",
                 custom_terms: list[str] | None = None) -> None:
        self.type = workflow_type
        self.language = language
        self.custom_terms = custom_terms or []

        self._phase = PhaseState()
        self.on_output: Callable[[str], None] | None = None
        self.on_phase_change: Callable[[PhaseState], None] | None = None

        self._recorder = AudioRecorder()
        self._thread: threading.Thread | None = None
        self._cancelled = False

    # MARK: - Zustand ---------------------------------------------------------

    @property
    def phase(self) -> PhaseState:
        return self._phase

    def _set_phase(self, new_phase: PhaseState) -> None:
        self._phase = new_phase
        if self.on_phase_change:
            self.on_phase_change(new_phase)

    @property
    def is_recording(self) -> bool:
        return self._recorder.is_recording

    @property
    def audio_level(self) -> float:
        return self._recorder.audio_level

    # MARK: - Steuerung (wie im Original) -------------------------------------

    def start(self) -> None:
        self._cancelled = False
        self._set_phase(PhaseState(Phase.RUNNING, "Aufnahme läuft ..."))
        self._recorder.start_recording()
        if self._recorder.error_message:
            self._set_phase(PhaseState(Phase.ERROR, self._recorder.error_message))

    def stop(self) -> None:
        if self._recorder.is_recording:
            self._recorder.stop_recording()
            if self._recorder.last_recording_duration < quality.MINIMUM_RECORDING_DURATION:
                self._recorder.discard_recording()
                self._set_phase(PhaseState(Phase.ERROR, "Keine Aufnahme erkannt."))
                return
            self._begin_processing()
        else:
            self._cancelled = True
            self._set_phase(PhaseState())

    def reset(self) -> None:
        self._cancelled = True
        if self._recorder.is_recording:
            self._recorder.stop_recording()
        self._recorder.discard_recording()
        self._set_phase(PhaseState())

    # MARK: - Verarbeitung im Hintergrund-Thread ------------------------------

    def _begin_processing(self) -> None:
        audio_path = self._recorder.recording_path
        if audio_path is None:
            self._set_phase(PhaseState(Phase.ERROR, "Keine Aufnahme vorhanden."))
            return

        duration = self._recorder.last_recording_duration
        # Eigennamen nur als Whisper-Hinweis nutzen, wenn lang genug (>= 0.9 s) — wie im Original.
        vocabulary_hints = list(self.custom_terms) if duration >= 0.9 else []

        self._thread = threading.Thread(
            target=self._run_processing,
            args=(audio_path, duration, vocabulary_hints),
            daemon=True,
        )
        self._thread.start()

    def _run_processing(self, audio_path: Path, duration: float, vocabulary_hints: list[str]) -> None:
        try:
            result = self._process(audio_path, duration, vocabulary_hints)
            self._check_cancelled()
            cleaned = result.strip()
            self._set_phase(PhaseState(Phase.DONE, cleaned))
            if self.on_output:
                self.on_output(cleaned)
        except WorkflowCancelled:
            pass  # Abbruch ist kein Fehler.
        except Exception as exc:  # noqa: BLE001 — jede Panne als Fehler-Phase melden
            self._set_phase(PhaseState(Phase.ERROR, str(exc)))
        finally:
            audio_path.unlink(missing_ok=True)

    def _check_cancelled(self) -> None:
        if self._cancelled:
            raise WorkflowCancelled()

    # MARK: - Von Unterklassen zu implementieren ------------------------------

    def _process(self, audio_path: Path, duration: float, vocabulary_hints: list[str]) -> str:
        """Verarbeitet die Aufnahme und gibt den fertigen Text zurück.
        Darf zwischendurch `self._set_phase(...)` für Statusmeldungen aufrufen."""
        raise NotImplementedError

    # Hilfsfunktion: prüft auf das "Keine Aufnahme erkannt."-Artefakt nach Whisper.
    def _reject_if_artifact(self, text: str, duration: float) -> str:
        cleaned = text.strip()
        if quality.is_likely_artifact(cleaned, duration):
            raise RuntimeError("Keine Aufnahme erkannt.")
        return cleaned
