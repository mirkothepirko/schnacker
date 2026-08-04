"""Tests für die Umbenennung Schnacker -> blablatext (Linux-Version).

Die Umbenennung berührt zwei Dinge, die man leicht durcheinanderbringt:

1. **Angezeigte Namen** (`display_name`) — die dürfen sich ändern, sie sind nur Text.
2. **Gespeicherte Werte** (die `Enum`-RawValues wie "dampfAblassen") — die dürfen sich
   *nicht* ändern. Sie stehen in der Einstellungsdatei und in den GNOME-Tastenkürzeln.
   Wer sie mit umbenennt, verliert bei bestehenden Nutzern Kürzel und Einstellungen.

Deshalb prüfen die Tests beides getrennt.
"""
import unittest
from pathlib import Path

from blitztext.models import PushToTalkTarget, WorkflowType
from blitztext.ui.popover import _LOGO_PFAD

_QUELLEN = Path(__file__).resolve().parents[1] / "blitztext"


class AngezeigteNamenTest(unittest.TestCase):
    def test_die_vier_workflows_heissen_wie_in_der_windows_version(self):
        self.assertEqual(
            [t.display_name for t in WorkflowType.main_menu_cases()],
            ["Diktat", "Lektorat", "Platt", "Basel"],
        )

    def test_push_to_talk_ziel_zeigt_denselben_namen_wie_der_workflow(self):
        # display_name leitet über den RawValue weiter — ohne zweite Tabelle,
        # die beim Umbenennen vergessen werden könnte.
        for ziel in PushToTalkTarget:
            if ziel is PushToTalkTarget.OFF:
                self.assertEqual(ziel.display_name, "Aus")
            else:
                self.assertEqual(ziel.display_name, ziel.workflow.display_name)


class GespeicherteWerteTest(unittest.TestCase):
    """Diese Werte sind der Vertrag mit der Einstellungsdatei — sie bleiben."""

    def test_workflow_rawvalues_unveraendert(self):
        self.assertEqual(
            [t.value for t in WorkflowType],
            ["transcription", "textImprover", "dampfAblassen", "emojiText"],
        )

    def test_push_to_talk_rawvalues_unveraendert(self):
        self.assertEqual(
            [z.value for z in PushToTalkTarget],
            ["off", "transcription", "textImprover", "dampfAblassen", "emojiText"],
        )


class OberflaecheTest(unittest.TestCase):
    def test_kopfzeilen_logo_liegt_wirklich_da(self):
        # popover.py zeigt das Logo nur, wenn die Datei existiert (if _LOGO_PFAD.exists()).
        # Ohne diesen Test würde ein falscher Pfad still zu einem Fenster ohne Logo führen.
        self.assertTrue(_LOGO_PFAD.exists(), f"Logo fehlt: {_LOGO_PFAD}")

    def test_kein_alter_name_mehr_im_quellcode(self):
        # Fängt vergessene Stellen bei der Umbenennung ab — inklusive
        # Kommentaren und Prompts, die der Nutzer indirekt zu sehen bekommt.
        treffer = [
            f"{pfad.relative_to(_QUELLEN)}:{nr}"
            for pfad in sorted(_QUELLEN.rglob("*.py"))
            for nr, zeile in enumerate(pfad.read_text(encoding="utf-8").splitlines(), 1)
            if "schnacker" in zeile.lower()
        ]
        self.assertEqual(treffer, [], "alter Name noch im Quellcode")


if __name__ == "__main__":
    unittest.main()
