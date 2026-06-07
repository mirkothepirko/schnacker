"""Zentraler App-Zustand — portiert aus AppState.swift.

Hält die Einstellungen, den aktiven Workflow und den Menüleisten-Status. Verbindet
die Workflows mit der Oberfläche und mit dem Einfügen.

Wichtig zum Threading: Die Workflows melden Phasenwechsel aus einem Hintergrund-
Thread. GTK darf aber nur aus dem Haupt-Thread heraus verändert werden. Deshalb
schleusen wir alle UI-relevanten Aktualisierungen mit `GLib.idle_add` zurück in
den Haupt-Thread (das ist GTKs sichere "mach das gleich im Hauptstrang"-Funktion).
"""

from __future__ import annotations

import threading
from enum import Enum
from typing import Callable

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib  # noqa: E402

from . import models
from .models import (
    LaunchSource,
    Phase,
    PhaseState,
    TranscriptionBackend,
    WorkflowType,
)
from .services import keychain
from .services import local_transcription as local
from .services import paste
from .services import settings_store
from .workflows.base import Workflow
from .workflows.dampf_ablassen import DampfAblassenWorkflow
from .workflows.emoji_text import EmojiTextWorkflow
from .workflows.text_improvement import TextImprovementWorkflow
from .workflows.transcription import TranscriptionWorkflow


class Page(str, Enum):
    MAIN = "main"
    ONBOARDING = "onboarding"
    SETTINGS = "settings"
    WORKFLOW = "workflow"


class StatusKind(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"


class MenuBarStatus:
    """Status fürs Menüleisten-Symbol (entspricht enum MenuBarStatus)."""

    def __init__(self, kind: StatusKind, workflow_type: WorkflowType | None = None) -> None:
        self.kind = kind
        self.workflow_type = workflow_type

    def __eq__(self, other) -> bool:
        return (isinstance(other, MenuBarStatus)
                and self.kind == other.kind
                and self.workflow_type == other.workflow_type)


class AppState:
    def __init__(self) -> None:
        self.settings = settings_store.load()

        self.active_workflow: Workflow | None = None
        self.page = Page.MAIN
        self.is_popover_shown = False
        self.menu_bar_status = MenuBarStatus(StatusKind.IDLE)
        self._active_launch_source = LaunchSource.MANUAL

        # Lokaler-Modell-Download-Status (für die Anzeige).
        self.local_model_downloading = False
        self.local_model_status_text: str | None = None
        self.local_model_error_text: str | None = None

        # Callbacks, die die Oberfläche setzt:
        self.on_menu_bar_status_change: Callable[[MenuBarStatus], None] | None = None
        self.on_ui_refresh: Callable[[], None] | None = None

        self._cleanup_source_id: int | None = None
        self._status_reset_source_id: int | None = None

        self._auto_select_fast_local_model_if_needed()

    # MARK: - Abgeleitete Werte -----------------------------------------------

    @property
    def is_configured(self) -> bool:
        return keychain.is_configured() or bool(local.installed_models())

    @property
    def should_show_onboarding(self) -> bool:
        return not self.is_configured and not self.settings.app.has_seen_onboarding

    @property
    def selected_local_model_name(self) -> str:
        return local.normalized_model_name(self.settings.app.selected_local_transcription_model_name)

    @property
    def selected_local_model_is_installed(self) -> bool:
        return local.is_model_installed(self.selected_local_model_name)

    @property
    def selected_local_model_display(self) -> str:
        return local.display_name(self.selected_local_model_name)

    def display_name(self, t: WorkflowType) -> str:
        """Eigener Name aus den Einstellungen, sonst der Standardname."""
        custom = {
            WorkflowType.TEXT_IMPROVER: self.settings.text_improvement.custom_name,
            WorkflowType.DAMPF_ABLASSEN: self.settings.dampf_ablassen.custom_name,
            WorkflowType.EMOJI_TEXT: self.settings.emoji_text.custom_name,
        }.get(t, "")
        custom = custom.strip()
        return custom if custom else t.display_name

    def workflow_subtitle(self, t: WorkflowType) -> str:
        if t is WorkflowType.TRANSCRIPTION:
            if self.settings.app.secure_local_mode_enabled:
                name = self.selected_local_model_name
                return (f"Lokal: {local.display_name(name)}." if local.is_model_installed(name)
                        else "Lokales Modell fehlt.")
            return "Online: Whisper über OpenAI."
        if t is WorkflowType.LOCAL_TRANSCRIPTION:
            return "Nur lokal. Kein Server."
        if self.settings.app.secure_local_mode_enabled:
            return "Im lokalen Modus pausiert."
        return t.subtitle

    # MARK: - Verfügbarkeit ----------------------------------------------------

    def is_workflow_available(self, t: WorkflowType) -> bool:
        if t is WorkflowType.LOCAL_TRANSCRIPTION:
            return self.selected_local_model_is_installed
        if t is WorkflowType.TRANSCRIPTION:
            return (self.selected_local_model_is_installed
                    if self.settings.app.secure_local_mode_enabled
                    else keychain.is_configured())
        # textImprover / dampfAblassen / emojiText
        return not self.settings.app.secure_local_mode_enabled and keychain.is_configured()

    # MARK: - Workflow starten/stoppen ----------------------------------------

    def start_workflow(self, t: WorkflowType, source: LaunchSource = LaunchSource.MANUAL) -> None:
        if not self.is_workflow_available(t):
            if source is LaunchSource.MANUAL:
                self.page = Page.SETTINGS
                self._refresh_ui()
            return

        if self.active_workflow:
            self.active_workflow.stop()
        self._cancel_cleanup()
        self._active_launch_source = source

        ti = self.settings.text_improvement
        if t is WorkflowType.TRANSCRIPTION:
            backend = (TranscriptionBackend.LOCAL if self.settings.app.secure_local_mode_enabled
                       else TranscriptionBackend.REMOTE)
            wf: Workflow = TranscriptionWorkflow(
                custom_terms=ti.custom_terms, language=self.settings.transcription.language,
                backend=backend, local_model_name=self.selected_local_model_name)
        elif t is WorkflowType.LOCAL_TRANSCRIPTION:
            wf = TranscriptionWorkflow(
                workflow_type=WorkflowType.LOCAL_TRANSCRIPTION, custom_terms=ti.custom_terms,
                language=self.settings.transcription.language, backend=TranscriptionBackend.LOCAL,
                local_model_name=self.selected_local_model_name)
        elif t is WorkflowType.TEXT_IMPROVER:
            wf = TextImprovementWorkflow(settings=ti, language=self.settings.transcription.language)
        elif t is WorkflowType.DAMPF_ABLASSEN:
            wf = DampfAblassenWorkflow(settings=self.settings.dampf_ablassen,
                                       custom_terms=ti.custom_terms,
                                       language=self.settings.transcription.language)
        else:  # EMOJI_TEXT
            wf = EmojiTextWorkflow(settings=self.settings.emoji_text, custom_terms=ti.custom_terms,
                                   language=self.settings.transcription.language)

        self._configure_workflow_handlers(wf)
        self.active_workflow = wf
        wf.start()

        self.page = Page.WORKFLOW if source.presents_workflow_page else Page.MAIN
        self._refresh_ui()

    def stop_current_workflow(self) -> None:
        if self.active_workflow:
            self.active_workflow.stop()

    def reset_current_workflow(self) -> None:
        if self.active_workflow:
            self.active_workflow.reset()
        self.active_workflow = None
        self._active_launch_source = LaunchSource.MANUAL
        self._cancel_cleanup()
        self.menu_bar_status = MenuBarStatus(StatusKind.IDLE)
        self.page = Page.MAIN
        self._emit_status()
        self._refresh_ui()

    # MARK: - Phasen & Ausgabe (laufen im Workflow-Thread) --------------------

    def _configure_workflow_handlers(self, wf: Workflow) -> None:
        wf.on_output = lambda text: self._handle_output(text, wf)
        wf.on_phase_change = lambda phase: GLib.idle_add(self._handle_phase_change, phase, wf)

    def _handle_output(self, text: str, wf: Workflow) -> None:
        # Läuft im Hintergrund-Thread. Einfügen/Kopieren darf hier passieren (reine IO).
        if self._active_launch_source is LaunchSource.HOTKEY_BACKGROUND:
            paste.paste_at_cursor(text)
        else:
            paste.copy_to_clipboard(text)
        GLib.idle_add(self._after_output)

    def _after_output(self) -> bool:
        if self._active_launch_source is LaunchSource.HOTKEY_BACKGROUND:
            self.page = Page.MAIN
        self._schedule_cleanup(1.05)
        self._refresh_ui()
        return False  # einmalig (GLib.idle_add wiederholt bei True)

    def _handle_phase_change(self, phase: PhaseState, wf: Workflow) -> bool:
        self._cancel_status_reset()
        if phase.phase is Phase.IDLE:
            if self.active_workflow is None:
                self.menu_bar_status = MenuBarStatus(StatusKind.IDLE)
        elif phase.phase is Phase.RUNNING:
            kind = StatusKind.RECORDING if wf.is_recording else StatusKind.PROCESSING
            self.menu_bar_status = MenuBarStatus(kind, wf.type)
        elif phase.phase is Phase.DONE:
            self.menu_bar_status = MenuBarStatus(StatusKind.SUCCESS, wf.type)
        elif phase.phase is Phase.ERROR:
            self.menu_bar_status = MenuBarStatus(StatusKind.ERROR, wf.type)
            if self._active_launch_source is LaunchSource.HOTKEY_BACKGROUND:
                self.active_workflow = None
                self.page = Page.MAIN
            self._schedule_status_reset(1.6)

        self._emit_status()
        self._refresh_ui()
        return False

    # MARK: - Aufräum-Timer (wie scheduleWorkflowCleanup im Original) ----------

    def _schedule_cleanup(self, delay: float) -> None:
        self._cancel_cleanup()
        self._cleanup_source_id = GLib.timeout_add(int(delay * 1000), self._do_cleanup)

    def _do_cleanup(self) -> bool:
        self._cleanup_source_id = None
        if self.active_workflow:
            self.active_workflow.reset()
        self.active_workflow = None
        self._active_launch_source = LaunchSource.MANUAL
        if not self.is_popover_shown:
            self.page = Page.MAIN
        self.menu_bar_status = MenuBarStatus(StatusKind.IDLE)
        self._emit_status()
        self._refresh_ui()
        return False

    def _cancel_cleanup(self) -> None:
        if self._cleanup_source_id is not None:
            GLib.source_remove(self._cleanup_source_id)
            self._cleanup_source_id = None

    def _schedule_status_reset(self, delay: float) -> None:
        self._cancel_status_reset()
        self._status_reset_source_id = GLib.timeout_add(int(delay * 1000), self._do_status_reset)

    def _do_status_reset(self) -> bool:
        self._status_reset_source_id = None
        if self.active_workflow is None or not self.active_workflow.phase.is_active:
            self.menu_bar_status = MenuBarStatus(StatusKind.IDLE)
            self._emit_status()
            self._refresh_ui()
        return False

    def _cancel_status_reset(self) -> None:
        if self._status_reset_source_id is not None:
            GLib.source_remove(self._status_reset_source_id)
            self._status_reset_source_id = None

    # MARK: - Lokaler Modus & Modell-Download ----------------------------------

    def enable_secure_local_mode(self) -> None:
        self.settings.app.secure_local_mode_enabled = True
        self.save_settings()
        if not self.selected_local_model_is_installed:
            self.install_selected_local_model()

    def install_selected_local_model(self) -> None:
        if self.local_model_downloading:
            return
        model_name = self.selected_local_model_name
        self.local_model_downloading = True
        self.local_model_status_text = "Download startet ..."
        self.local_model_error_text = None
        self._refresh_ui()

        def worker() -> None:
            try:
                def status(msg: str) -> None:
                    self.local_model_status_text = msg
                    GLib.idle_add(self._refresh_ui)
                local.download_and_install(model_name, status_handler=status)
                self.settings.app.secure_local_mode_enabled = True
                self.local_model_downloading = False
                self.local_model_status_text = f"{local.display_name(model_name)} ist installiert."
                self.local_model_error_text = None
            except Exception as exc:  # noqa: BLE001
                self.local_model_downloading = False
                self.local_model_status_text = None
                self.local_model_error_text = str(exc)
            GLib.idle_add(self._after_model_change)

        threading.Thread(target=worker, daemon=True).start()

    def _after_model_change(self) -> bool:
        self.save_settings()
        self._refresh_ui()
        return False

    def _auto_select_fast_local_model_if_needed(self) -> None:
        app = self.settings.app
        if app.has_auto_selected_fast_local_model:
            return
        if local.is_model_installed(models.RECOMMENDED_FAST_MODEL_NAME):
            app.selected_local_transcription_model_name = models.RECOMMENDED_FAST_MODEL_NAME
            app.has_auto_selected_fast_local_model = True

    # MARK: - Onboarding & Sonstiges ------------------------------------------

    def mark_onboarding_seen(self) -> None:
        if not self.settings.app.has_seen_onboarding:
            self.settings.app.has_seen_onboarding = True
            self.save_settings()

    def copy_to_clipboard(self, text: str) -> None:
        paste.copy_to_clipboard(text)

    # MARK: - Persistenz -------------------------------------------------------

    def save_settings(self) -> None:
        settings_store.save(self.settings)

    # MARK: - UI-Benachrichtigung ---------------------------------------------

    def _emit_status(self) -> None:
        if self.on_menu_bar_status_change:
            self.on_menu_bar_status_change(self.menu_bar_status)

    def _refresh_ui(self) -> None:
        if self.on_ui_refresh:
            self.on_ui_refresh()
