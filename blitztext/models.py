"""Datentypen & Einstellungen — 1:1 portiert aus WorkflowProtocol.swift.

Hier stehen die "Steckbriefe" der Workflows (Namen, Untertitel, Farben) und die
Einstellungs-Strukturen mit ihren Standardwerten. Diese Texte und Defaults sind
absichtlich exakt wie im Original-Code übernommen, damit sich die App identisch verhält.

In Python nutzen wir `Enum` (eine feste Auswahl von Werten) und `dataclass`
(eine einfache Klasse, die nur Daten hält) statt Swifts `enum`/`struct`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# MARK: - Workflow-Typen ------------------------------------------------------


class WorkflowType(str, Enum):
    """Die vier Workflows. (str, Enum) heißt: jeder Wert ist auch ein Text,
    so lässt er sich leicht speichern/übertragen — wie Swifts `String`-RawValue."""

    TRANSCRIPTION = "transcription"
    TEXT_IMPROVER = "textImprover"
    DAMPF_ABLASSEN = "dampfAblassen"
    EMOJI_TEXT = "emojiText"

    @staticmethod
    def main_menu_cases() -> list["WorkflowType"]:
        """Alle Workflows — die Reihenfolge bestimmt Menü und Tastenkürzel."""
        return list(WorkflowType)

    @property
    def display_name(self) -> str:
        return {
            WorkflowType.TRANSCRIPTION: "Schnacker",
            WorkflowType.TEXT_IMPROVER: "Schnacker+",
            WorkflowType.DAMPF_ABLASSEN: "Schnacker Platt",
            WorkflowType.EMOJI_TEXT: "Schnacker Basel",
        }[self]

    @property
    def subtitle(self) -> str:
        return {
            WorkflowType.TRANSCRIPTION: "Sprache rein. Text raus.",
            WorkflowType.TEXT_IMPROVER: "Geschrieben sprechen.",
            WorkflowType.DAMPF_ABLASSEN: "Hochdeutsch rein. Platt raus.",
            WorkflowType.EMOJI_TEXT: "Hochdeutsch rein. Baseldütsch raus.",
        }[self]


# MARK: - Workflow-Zustand ----------------------------------------------------


class Phase(str, Enum):
    """Die vier Phasen eines Workflows (wie WorkflowPhase im Original).
    Die Begleittexte/Ergebnisse hängen wir separat an (siehe PhaseState)."""

    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class PhaseState:
    """Phase + zugehöriger Text (z.B. Statusmeldung, Ergebnis oder Fehlertext).
    Entspricht Swifts `enum WorkflowPhase` mit assoziierten Werten."""

    phase: Phase = Phase.IDLE
    text: str = ""

    @property
    def is_active(self) -> bool:
        return self.phase is not Phase.IDLE


class LaunchSource(str, Enum):
    """Wie wurde der Workflow gestartet? Wichtig fürs Auto-Einfügen:
    Per Tastenkürzel (Hintergrund) fügen wir automatisch ein; per Fenster nicht."""

    MANUAL = "manual"            # über das Popover-Fenster
    HOTKEY_BACKGROUND = "hotkeyBackground"  # über ein GNOME-Tastenkürzel

    @property
    def presents_workflow_page(self) -> bool:
        return self is LaunchSource.MANUAL


class TranscriptionBackend(str, Enum):
    REMOTE = "remote"  # OpenAI Whisper
    LOCAL = "local"    # faster-whisper auf diesem Rechner


# MARK: - Einstellungen (Defaults exakt wie im Original) ----------------------


# Standard-System-Prompt für "Schnacker Platt" — übersetzt Hochdeutsch nach Plattdeutsch.
# (Workflow heißt intern weiter "dampfAblassen", damit Tastenkürzel/Settings stabil bleiben.)
DAMPF_ABLASSEN_DEFAULT_PROMPT = (
    "Du bist ein Übersetzer für Plattdeutsch (Niederdeutsch). Du bekommst einen auf Hochdeutsch "
    "gesprochenen Text. Übersetze ihn in natürliches, gut lesbares Plattdeutsch. Bewahre Sinn, "
    "Inhalt und Tonfall des Originals. Übersetze sinngemäß und idiomatisch, nicht Wort für Wort, "
    "und nutze typische plattdeutsche Wendungen, wo sie passen. Eigennamen, Zahlen, Datums- und "
    "Uhrzeitangaben sowie Fachbegriffe bleiben unverändert. Gib NUR den plattdeutschen Text "
    "zurück — keine Erklärungen und keine hochdeutsche Fassung daneben."
)


# Standard-System-Prompt für "Schnacker Basel" — übersetzt Hochdeutsch nach Baseldütsch.
# (Workflow heißt intern weiter "emojiText", damit Tastenkürzel/Settings stabil bleiben.)
BASEL_DEFAULT_PROMPT = (
    "Du bist ein Übersetzer für Baseldütsch (das alemannische Schweizerdeutsch aus dem Raum "
    "Basel). Du bekommst einen auf Hochdeutsch gesprochenen Text. Übersetze ihn in natürliches, "
    "gut lesbares Baseldütsch, wie man es in der Stadt Basel spricht. Bewahre Sinn, Inhalt und "
    "Tonfall des Originals. Übersetze sinngemäß und idiomatisch, nicht Wort für Wort, und nutze "
    "Basel-typische Wörter und Schreibweisen (z. B. 'y' für langes i wie in 'Zyt', 'Wyn'; niemals "
    "'ß', stattdessen 'ss'). Eigennamen, Zahlen, Datums- und Uhrzeitangaben sowie Fachbegriffe "
    "bleiben unverändert. Gib NUR den baseldütschen Text zurück — keine Erklärungen und keine "
    "hochdeutsche Fassung daneben."
)


# Standard-Modellname für die lokale Transkription (empfohlenes schnelles Modell).
RECOMMENDED_FAST_MODEL_NAME = "small"


class TextTone(str, Enum):
    FORMAL = "formal"
    NEUTRAL = "neutral"
    CASUAL = "casual"

    @property
    def display_name(self) -> str:
        return {TextTone.FORMAL: "Formell", TextTone.NEUTRAL: "Neutral", TextTone.CASUAL: "Locker"}[self]


@dataclass
class AppSettings:
    has_seen_onboarding: bool = False
    secure_local_mode_enabled: bool = False
    selected_local_transcription_model_name: str = RECOMMENDED_FAST_MODEL_NAME
    has_auto_selected_fast_local_model: bool = False


@dataclass
class TranscriptionSettings:
    language: str = "de"


@dataclass
class DampfAblassenSettings:
    system_prompt: str = DAMPF_ABLASSEN_DEFAULT_PROMPT
    custom_name: str = ""


@dataclass
class EmojiTextSettings:
    system_prompt: str = BASEL_DEFAULT_PROMPT
    custom_name: str = ""


@dataclass
class TextImprovementSettings:
    system_prompt: str = ""
    custom_terms: list[str] = field(default_factory=list)
    context: str = ""
    tone: TextTone = TextTone.NEUTRAL
    custom_name: str = ""
