"""Tests für die Qualitätsprüfung der Aufnahme.

Diese Regeln entscheiden, ob eine Whisper-Antwort als "Halluzination" verworfen
wird. Die Grenzwerte (0.3 / 0.55 / 0.8 Sekunden, 5 Wörter, 32 / 56 Zeichen) sind
aus dem Original übernommen — die Tests prüfen genau **an** der Grenze, weil dort
Vertipper wie `<` statt `<=` sonst unbemerkt bleiben.
"""

from __future__ import annotations

import unittest

from blitztext.services import transcription_quality as quality


class MindestlaengeTest(unittest.TestCase):
    """Die Grenze selbst wird in test_workflows geprüft (dort wird sie angewandt)."""

    def test_mindestlaenge_ist_drei_zehntel_sekunden(self) -> None:
        self.assertEqual(quality.MINIMUM_RECORDING_DURATION, 0.3)


class ArtifactTest(unittest.TestCase):

    def test_umgebende_leerzeichen_werden_ignoriert(self) -> None:
        self.assertFalse(quality.is_likely_artifact("  Hallo Welt \n", 5.0))

    def test_leerer_text_ist_artefakt(self) -> None:
        self.assertTrue(quality.is_likely_artifact("", 5.0))
        self.assertTrue(quality.is_likely_artifact("   \n ", 5.0))

    def test_text_ohne_buchstaben_ist_artefakt(self) -> None:
        self.assertTrue(quality.is_likely_artifact("... !!! 123", 5.0))

    def test_umlaute_zaehlen_als_buchstaben(self) -> None:
        # Wichtig für Deutsch: ä/ö/ü/ß dürfen nicht als "keine Buchstaben" gelten.
        self.assertFalse(quality.is_likely_artifact("Öl", 5.0))
        self.assertFalse(quality.is_likely_artifact("Straße", 5.0))

    def test_nichtlateinische_buchstaben_zaehlen_auch(self) -> None:
        self.assertFalse(quality.is_likely_artifact("Привет", 5.0))

    def test_kurze_aufnahme_mit_vielen_woertern_ist_artefakt(self) -> None:
        # < 0.55 s und >= 5 Wörter
        self.assertTrue(quality.is_likely_artifact("a b c d e", 0.5))

    def test_kurze_aufnahme_mit_vier_woertern_ist_ok(self) -> None:
        self.assertFalse(quality.is_likely_artifact("a b c d", 0.5))

    def test_kurze_aufnahme_mit_vielen_zeichen_ist_artefakt(self) -> None:
        # < 0.55 s und >= 32 Zeichen (hier: 32 Zeichen ohne Wortgrenze)
        self.assertTrue(quality.is_likely_artifact("x" * 32, 0.5))

    def test_kurze_aufnahme_mit_31_zeichen_ist_ok(self) -> None:
        self.assertFalse(quality.is_likely_artifact("x" * 31, 0.5))

    def test_ab_055_sekunden_gilt_die_wortregel_nicht_mehr(self) -> None:
        self.assertFalse(quality.is_likely_artifact("a b c d e", 0.55))

    def test_mittellange_aufnahme_mit_56_zeichen_ist_artefakt(self) -> None:
        # < 0.8 s und >= 56 Zeichen
        self.assertTrue(quality.is_likely_artifact("x" * 56, 0.79))

    def test_mittellange_aufnahme_mit_55_zeichen_ist_ok(self) -> None:
        self.assertFalse(quality.is_likely_artifact("x" * 55, 0.79))

    def test_ab_08_sekunden_gilt_die_zeichenregel_nicht_mehr(self) -> None:
        self.assertFalse(quality.is_likely_artifact("x" * 200, 0.8))

    def test_normaler_satz_ist_kein_artefakt(self) -> None:
        self.assertFalse(quality.is_likely_artifact(
            "Das ist ein völlig normaler diktierter Satz.", 4.2))


if __name__ == "__main__":
    unittest.main()
