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
    """Die fünf Workflows. (str, Enum) heißt: jeder Wert ist auch ein Text,
    so lässt er sich leicht speichern/übertragen — wie Swifts `String`-RawValue."""

    TRANSCRIPTION = "transcription"
    LOCAL_TRANSCRIPTION = "localTranscription"
    TEXT_IMPROVER = "textImprover"
    DAMPF_ABLASSEN = "dampfAblassen"
    EMOJI_TEXT = "emojiText"

    @staticmethod
    def main_menu_cases() -> list["WorkflowType"]:
        """Im Hauptmenü gezeigte Workflows (ohne den separaten Lokal-Workflow)."""
        return [t for t in WorkflowType if t is not WorkflowType.LOCAL_TRANSCRIPTION]

    @property
    def display_name(self) -> str:
        return {
            WorkflowType.TRANSCRIPTION: "Blitztext",
            WorkflowType.LOCAL_TRANSCRIPTION: "Blitztext Lokal",
            WorkflowType.TEXT_IMPROVER: "Blitztext+",
            WorkflowType.DAMPF_ABLASSEN: "Blitztext $%&!",
            WorkflowType.EMOJI_TEXT: "Blitztext :)",
        }[self]

    @property
    def icon(self) -> str:
        """Symbolname. Im Original SF-Symbols; hier merken wir uns einen
        sprechenden Namen, das UI bildet ihn auf ein GTK-Symbol ab."""
        return {
            WorkflowType.TRANSCRIPTION: "mic",
            WorkflowType.LOCAL_TRANSCRIPTION: "lock",
            WorkflowType.TEXT_IMPROVER: "text-check",
            WorkflowType.DAMPF_ABLASSEN: "flame",
            WorkflowType.EMOJI_TEXT: "smiley",
        }[self]

    @property
    def subtitle(self) -> str:
        return {
            WorkflowType.TRANSCRIPTION: "Sprache rein. Text raus.",
            WorkflowType.LOCAL_TRANSCRIPTION: "Nur lokal. Kein Server.",
            WorkflowType.TEXT_IMPROVER: "Geschrieben sprechen.",
            WorkflowType.DAMPF_ABLASSEN: "Frust rein. Entspannt raus.",
            WorkflowType.EMOJI_TEXT: "Text rein. Emojis dazu.",
        }[self]

    @property
    def accent_color(self) -> str:
        return {
            WorkflowType.TRANSCRIPTION: "blue",
            WorkflowType.LOCAL_TRANSCRIPTION: "green",
            WorkflowType.TEXT_IMPROVER: "purple",
            WorkflowType.DAMPF_ABLASSEN: "orange",
            WorkflowType.EMOJI_TEXT: "cyan",
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

    @staticmethod
    def idle() -> "PhaseState":
        return PhaseState(Phase.IDLE, "")

    @staticmethod
    def running(message: str) -> "PhaseState":
        return PhaseState(Phase.RUNNING, message)

    @staticmethod
    def done(result: str) -> "PhaseState":
        return PhaseState(Phase.DONE, result)

    @staticmethod
    def error(message: str) -> "PhaseState":
        return PhaseState(Phase.ERROR, message)


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


# MARK: - Tastenkürzel-Modus --------------------------------------------------


class HotkeyMode(str, Enum):
    HOLD = "hold"      # Original: halten = aufnehmen. Unter Wayland wie TOGGLE (Hinweis im UI).
    TOGGLE = "toggle"  # 1x drücken = starten, nochmal/Escape = stoppen

    @property
    def display_name(self) -> str:
        return {HotkeyMode.HOLD: "Halten", HotkeyMode.TOGGLE: "Drücken"}[self]

    @property
    def description(self) -> str:
        return {
            HotkeyMode.HOLD: "Tasten halten zum Aufnehmen, loslassen zum Stoppen",
            HotkeyMode.TOGGLE: "Einmal drücken zum Starten, nochmal oder Escape zum Stoppen",
        }[self]


# MARK: - Einstellungen (Defaults exakt wie im Original) ----------------------


# Der lange Standard-System-Prompt für "Blitztext $%&!" — wörtlich aus DampfAblassenSettings.
DAMPF_ABLASSEN_DEFAULT_PROMPT = (
    "Du erhältst ein emotional gesprochenes Transkript. Erkenne zuerst das eigentliche Ziel, "
    "Anliegen und den wahren Frust der Person. Formuliere daraus eine klare, respektvolle und "
    "wirksame Nachricht, mit der die Person ihr Ziel eher erreicht. Bewahre relevante Fakten, "
    "konkrete Probleme, Grenzen, Erwartungen und die nötige Dringlichkeit. Entferne Beleidigungen, "
    "Drohungen, Sarkasmus, Unterstellungen und unnötige Eskalation. Wenn mehrere Vorwürfe genannt "
    "werden, verdichte sie auf die entscheidenden Kernpunkte. Der Ton soll ruhig, menschlich, "
    "bestimmt und lösungsorientiert sein. Gib NUR die fertige Nachricht zurück."
)


class TextTone(str, Enum):
    FORMAL = "formal"
    NEUTRAL = "neutral"
    CASUAL = "casual"

    @property
    def display_name(self) -> str:
        return {TextTone.FORMAL: "Formell", TextTone.NEUTRAL: "Neutral", TextTone.CASUAL: "Locker"}[self]


class EmojiDensity(str, Enum):
    WENIG = "wenig"
    MITTEL = "mittel"
    VIEL = "viel"

    @property
    def display_name(self) -> str:
        return {EmojiDensity.WENIG: "Wenig", EmojiDensity.MITTEL: "Mittel", EmojiDensity.VIEL: "Viel"}[self]


# Standard-Modellname für die lokale Transkription (empfohlenes schnelles Modell).
RECOMMENDED_FAST_MODEL_NAME = "small"


@dataclass
class AppSettings:
    hotkey_mode: HotkeyMode = HotkeyMode.HOLD
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
    emoji_density: EmojiDensity = EmojiDensity.MITTEL
    custom_name: str = ""


@dataclass
class TextImprovementSettings:
    system_prompt: str = ""
    custom_terms: list[str] = field(default_factory=list)
    context: str = ""
    tone: TextTone = TextTone.NEUTRAL
    custom_name: str = ""
