"""Tests für Schlüsselbund, Zwischenablage/Einfügen und die lokalen Modell-Namen."""

from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from blitztext.services import keychain
from blitztext.services import local_transcription as local
from blitztext.services import paste


class KeychainTest(unittest.TestCase):

    def setUp(self) -> None:
        keychain.invalidate_cache()
        self.addCleanup(keychain.invalidate_cache)

    def test_speichern_und_lesen(self) -> None:
        with mock.patch.object(keychain.keyring, "set_password") as setzen, \
             mock.patch.object(keychain.keyring, "get_password", return_value="sk-abc"):
            keychain.save(keychain.KeychainKey.OPEN_AI_API_KEY, "sk-abc")
            self.assertEqual(keychain.load(keychain.KeychainKey.OPEN_AI_API_KEY), "sk-abc")
        setzen.assert_called_once()

    def test_gelesener_wert_wird_zwischengespeichert(self) -> None:
        """Der Schlüsselbund darf nicht bei jedem Tastendruck befragt werden."""
        with mock.patch.object(keychain.keyring, "get_password", return_value="sk-abc") as holen:
            keychain.load(keychain.KeychainKey.OPEN_AI_API_KEY)
            keychain.load(keychain.KeychainKey.OPEN_AI_API_KEY)
        holen.assert_called_once()

    def test_cache_leeren_erzwingt_neues_lesen(self) -> None:
        with mock.patch.object(keychain.keyring, "get_password", return_value="sk-abc") as holen:
            keychain.load(keychain.KeychainKey.OPEN_AI_API_KEY)
            keychain.invalidate_cache()
            keychain.load(keychain.KeychainKey.OPEN_AI_API_KEY)
        self.assertEqual(holen.call_count, 2)

    def test_kaputter_schluesselbund_gibt_none_statt_abzustuerzen(self) -> None:
        with mock.patch.object(keychain.keyring, "get_password",
                               side_effect=keychain.keyring.errors.KeyringError("kein Dienst")):
            self.assertIsNone(keychain.load(keychain.KeychainKey.OPEN_AI_API_KEY))

    def test_is_configured_nur_bei_vorhandenem_key(self) -> None:
        with mock.patch.object(keychain.keyring, "get_password", return_value="sk-abc"):
            self.assertTrue(keychain.is_configured())
        keychain.invalidate_cache()
        with mock.patch.object(keychain.keyring, "get_password", return_value=None):
            self.assertFalse(keychain.is_configured())
        keychain.invalidate_cache()
        with mock.patch.object(keychain.keyring, "get_password", return_value=""):
            self.assertFalse(keychain.is_configured())


class PasteTest(unittest.TestCase):

    def test_copy_ohne_wl_copy_meldet_fehlschlag(self) -> None:
        with mock.patch.object(paste.shutil, "which", return_value=None):
            self.assertFalse(paste.copy_to_clipboard("Text"))

    def test_copy_ruft_wl_copy_mit_trenner_auf(self) -> None:
        """Das '--' verhindert, dass Text der mit '-' beginnt als Option gilt."""
        with mock.patch.object(paste.shutil, "which", return_value="/usr/bin/wl-copy"), \
             mock.patch.object(paste.subprocess, "run") as run:
            self.assertTrue(paste.copy_to_clipboard("-n"))
        self.assertEqual(run.call_args.args[0], ["wl-copy", "--", "-n"])

    def test_copy_faengt_fehler_von_wl_copy_ab(self) -> None:
        with mock.patch.object(paste.shutil, "which", return_value="/usr/bin/wl-copy"), \
             mock.patch.object(paste.subprocess, "run",
                               side_effect=subprocess.SubprocessError("weg")):
            self.assertFalse(paste.copy_to_clipboard("Text"))

    def test_auto_paste_verfuegbar_wenn_ydotool_da_ist(self) -> None:
        with mock.patch.object(paste.shutil, "which", return_value="/usr/bin/ydotool"):
            self.assertTrue(paste.is_auto_paste_available())
        with mock.patch.object(paste.shutil, "which", return_value=None):
            self.assertFalse(paste.is_auto_paste_available())

    def test_einfuegen_kopiert_und_drueckt_strg_v(self) -> None:
        with mock.patch.object(paste.shutil, "which", return_value="/usr/bin/x"), \
             mock.patch.object(paste, "time"), \
             mock.patch.object(paste.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stderr="")
            ergebnis = paste.paste_at_cursor("Text")
        aufrufe = [c.args[0] for c in run.call_args_list]
        self.assertIn(["wl-copy", "--", "Text"], aufrufe)
        self.assertIn(["ydotool", "key", "ctrl+v"], aufrufe)
        self.assertTrue(ergebnis.pasted)
        self.assertTrue(ergebnis.copied)

    def test_einfuegen_ohne_ydotool_scheitert_leise(self) -> None:
        """Der Text muss trotzdem in der Zwischenablage landen (Fallback Strg+V per Hand)."""
        def which(name):
            return "/usr/bin/wl-copy" if name == "wl-copy" else None

        with mock.patch.object(paste.shutil, "which", side_effect=which), \
             mock.patch.object(paste, "time"), \
             mock.patch.object(paste.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stderr="")
            ergebnis = paste.paste_at_cursor("Text")
        self.assertEqual([c.args[0] for c in run.call_args_list], [["wl-copy", "--", "Text"]])
        self.assertFalse(ergebnis.pasted)
        self.assertTrue(ergebnis.copied)

    def test_einfuegen_meldet_fehlende_rechte(self) -> None:
        with mock.patch.object(paste.shutil, "which", return_value="/usr/bin/x"), \
             mock.patch.object(paste, "time"), \
             mock.patch.object(paste.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=1, stderr="Permission denied")
            ergebnis = paste.paste_at_cursor("Text")
        self.assertFalse(ergebnis.pasted)


class LocalModelNamesTest(unittest.TestCase):

    def test_unbekannter_modellname_faellt_auf_small_zurueck(self) -> None:
        self.assertEqual(local.normalized_model_name("gibt-es-nicht"), "small")
        self.assertEqual(local.normalized_model_name(""), "small")
        self.assertEqual(local.normalized_model_name("  large-v3  "), "large-v3")

    def test_anzeigenamen_der_drei_modelle(self) -> None:
        self.assertEqual(local.display_name("small"), "Whisper Small")
        self.assertEqual(local.display_name("large-v3"), "Whisper Large v3")
        self.assertEqual(local.display_name("large-v3-turbo"), "Whisper Large v3 Turbo")

    def test_model_options_liefert_alle_drei_in_reihenfolge(self) -> None:
        self.assertEqual(local.model_options(), ["small", "large-v3", "large-v3-turbo"])

    def test_model_options_gibt_eine_kopie_zurueck(self) -> None:
        """Sonst könnte die Oberfläche versehentlich die Original-Liste leeren."""
        local.model_options().clear()
        self.assertEqual(len(local.model_options()), 3)

    def test_installiert_erkennt_die_model_bin(self) -> None:
        with mock.patch.object(local, "MODELS_DIR") as models_dir:
            ordner = models_dir.__truediv__.return_value
            ordner.is_dir.return_value = True
            ordner.glob.return_value = iter(["snapshots/abc/model.bin"])
            self.assertTrue(local.is_model_installed("small"))

    def test_nicht_installiert_wenn_ordner_fehlt(self) -> None:
        with mock.patch.object(local, "MODELS_DIR") as models_dir:
            models_dir.__truediv__.return_value.is_dir.return_value = False
            self.assertFalse(local.is_model_installed("small"))

    def test_resolved_model_name_nimmt_ein_installiertes_wenn_das_gewuenschte_fehlt(self) -> None:
        with mock.patch.object(local, "is_model_installed", lambda n: n == "large-v3"):
            self.assertEqual(local.resolved_model_name("small"), "large-v3")

    def test_resolved_model_name_bleibt_beim_wunsch_wenn_nichts_installiert_ist(self) -> None:
        with mock.patch.object(local, "is_model_installed", lambda _n: False):
            self.assertEqual(local.resolved_model_name("large-v3"), "large-v3")


if __name__ == "__main__":
    unittest.main()
