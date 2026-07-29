"""Tests für den Einstellungs-Speicher.

Wichtigster Punkt: Die JSON-Schlüssel auf der Platte sind ein **Vertrag**.
Wer sie umbenennt, verliert beim nächsten Start die Einstellungen aller Nutzer.
Deshalb nagelt `test_json_keys_exakt_wie_bisher` die Schlüsselnamen fest.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from blitztext import models
from blitztext.services import settings_store


class SettingsStoreTest(unittest.TestCase):

    def setUp(self) -> None:
        # Jeder Test bekommt ein eigenes, leeres Verzeichnis (kein Zugriff auf
        # die echte ~/.config des Rechners).
        self._tmp = TemporaryDirectory()
        tmp_path = Path(self._tmp.name)
        patches = {
            "CONFIG_DIR": tmp_path / "config",
            "MODELS_DIR": tmp_path / "models",
            "SETTINGS_PATH": tmp_path / "config" / "settings.json",
        }
        for name, value in patches.items():
            p = mock.patch.object(settings_store, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.settings_path = patches["SETTINGS_PATH"]
        self.addCleanup(self._tmp.cleanup)

    # MARK: - Laden ohne Datei / mit kaputter Datei ----------------------------

    def test_ohne_datei_kommen_standardwerte(self) -> None:
        bundle = settings_store.load()
        self.assertEqual(bundle.transcription.language, "de")
        self.assertFalse(bundle.app.has_seen_onboarding)
        self.assertFalse(bundle.app.secure_local_mode_enabled)
        self.assertEqual(bundle.app.selected_local_transcription_model_name, "small")
        self.assertEqual(bundle.text_improvement.tone, models.TextTone.NEUTRAL)
        self.assertEqual(bundle.text_improvement.custom_terms, [])
        # Die langen Mundart-Prompts sind Standardwerte, nicht leer.
        self.assertEqual(bundle.dampf_ablassen.system_prompt,
                         models.DAMPF_ABLASSEN_DEFAULT_PROMPT)
        self.assertEqual(bundle.emoji_text.system_prompt, models.BASEL_DEFAULT_PROMPT)

    def test_kaputte_json_datei_fuehrt_zu_standardwerten(self) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text("{ das ist kein JSON", encoding="utf-8")
        self.assertEqual(settings_store.load().transcription.language, "de")

    def test_json_das_kein_objekt_ist_fuehrt_zu_standardwerten(self) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text("[1, 2, 3]", encoding="utf-8")
        self.assertEqual(settings_store.load().transcription.language, "de")

    # MARK: - Hin und zurück ---------------------------------------------------

    def test_speichern_und_laden_ergibt_dieselben_werte(self) -> None:
        bundle = settings_store.SettingsBundle()
        bundle.app.has_seen_onboarding = True
        bundle.app.secure_local_mode_enabled = True
        bundle.app.selected_local_transcription_model_name = "large-v3"
        bundle.app.has_auto_selected_fast_local_model = True
        bundle.transcription.language = "en"
        bundle.text_improvement.system_prompt = "Sei knapp."
        bundle.text_improvement.custom_terms = ["Flötotto", "FLEX TABLE"]
        bundle.text_improvement.context = "E-Mails"
        bundle.text_improvement.tone = models.TextTone.FORMAL
        bundle.text_improvement.custom_name = "Mein Lektor"
        bundle.dampf_ablassen.system_prompt = "Platt bitte."
        bundle.dampf_ablassen.custom_name = "Platt"
        bundle.emoji_text.system_prompt = "Basel bitte."
        bundle.emoji_text.custom_name = "Basel"

        settings_store.save(bundle)
        wieder = settings_store.load()

        self.assertTrue(wieder.app.has_seen_onboarding)
        self.assertTrue(wieder.app.secure_local_mode_enabled)
        self.assertEqual(wieder.app.selected_local_transcription_model_name, "large-v3")
        self.assertTrue(wieder.app.has_auto_selected_fast_local_model)
        self.assertEqual(wieder.transcription.language, "en")
        self.assertEqual(wieder.text_improvement.system_prompt, "Sei knapp.")
        self.assertEqual(wieder.text_improvement.custom_terms, ["Flötotto", "FLEX TABLE"])
        self.assertEqual(wieder.text_improvement.context, "E-Mails")
        self.assertEqual(wieder.text_improvement.tone, models.TextTone.FORMAL)
        self.assertEqual(wieder.text_improvement.custom_name, "Mein Lektor")
        self.assertEqual(wieder.dampf_ablassen.system_prompt, "Platt bitte.")
        self.assertEqual(wieder.dampf_ablassen.custom_name, "Platt")
        self.assertEqual(wieder.emoji_text.system_prompt, "Basel bitte.")
        self.assertEqual(wieder.emoji_text.custom_name, "Basel")

    def test_json_keys_exakt_wie_bisher(self) -> None:
        """Der Vertrag mit bereits gespeicherten Dateien: camelCase-Schlüssel."""
        settings_store.save(settings_store.SettingsBundle())
        raw = json.loads(self.settings_path.read_text(encoding="utf-8"))

        self.assertEqual(set(raw), {"app", "transcription", "textImprovement",
                                    "dampfAblassen", "emojiText"})
        # "hotkeyMode" ist absichtlich weg: die Einstellung hatte keine Wirkung.
        self.assertEqual(set(raw["app"]), {
            "hasSeenOnboarding", "secureLocalModeEnabled",
            "selectedLocalTranscriptionModelName", "hasAutoSelectedFastLocalModel",
        })
        self.assertEqual(set(raw["transcription"]), {"language"})
        self.assertEqual(set(raw["textImprovement"]),
                         {"systemPrompt", "customTerms", "context", "tone", "customName"})
        self.assertEqual(set(raw["dampfAblassen"]), {"systemPrompt", "customName"})
        # "emojiDensity" ist absichtlich weg: Rest des früheren Emoji-Workflows.
        self.assertEqual(set(raw["emojiText"]), {"systemPrompt", "customName"})

    def test_alte_datei_mit_unbekannten_feldern_wird_gelesen(self) -> None:
        """Vorwärts-/rückwärtskompatibel: Unbekanntes ignorieren, Fehlendes = Standard."""
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(json.dumps({
            # hotkeyMode/emojiDensity: Felder aus einer älteren Version, heute entfernt.
            "app": {"hasSeenOnboarding": True, "hotkeyMode": "toggle", "quatsch": 1},
            "transcription": {"language": "fr"},
            "textImprovement": {"tone": "casual"},
            "emojiText": {"systemPrompt": "Basel", "emojiDensity": "viel"},
        }), encoding="utf-8")

        bundle = settings_store.load()
        self.assertTrue(bundle.app.has_seen_onboarding)
        self.assertEqual(bundle.transcription.language, "fr")
        self.assertEqual(bundle.text_improvement.tone, models.TextTone.CASUAL)
        self.assertEqual(bundle.emoji_text.system_prompt, "Basel")
        # Fehlende Gruppe -> Standardwert
        self.assertEqual(bundle.dampf_ablassen.system_prompt,
                         models.DAMPF_ABLASSEN_DEFAULT_PROMPT)

    def test_unbekannter_enum_wert_fuehrt_zum_standard(self) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(
            json.dumps({"textImprovement": {"tone": "gibt-es-nicht"}}), encoding="utf-8")
        self.assertEqual(settings_store.load().text_improvement.tone, models.TextTone.NEUTRAL)

    def test_custom_terms_kein_array_wird_zur_leeren_liste(self) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(
            json.dumps({"textImprovement": {"customTerms": "kaputt"}}), encoding="utf-8")
        self.assertEqual(settings_store.load().text_improvement.custom_terms, [])

    def test_speichern_hinterlaesst_keine_temp_datei(self) -> None:
        """Geschrieben wird über eine .tmp-Datei; danach darf sie nicht liegen bleiben."""
        settings_store.save(settings_store.SettingsBundle())
        uebrig = [p.name for p in self.settings_path.parent.iterdir()]
        self.assertEqual(uebrig, ["settings.json"])


if __name__ == "__main__":
    unittest.main()
