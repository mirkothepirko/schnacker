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
from tempfile import TemporaryDirectory
from unittest import mock

from blablatext.models import PushToTalkTarget, WorkflowType
from blablatext.services import keychain, settings_store
from blablatext.ui.popover import _LOGO_PFAD

_QUELLEN = Path(__file__).resolve().parents[1] / "blablatext"


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
        # Erlaubt bleibt nur, wo die alten Namen bewusst stehen: die Herkunfts-
        # angabe zur macOS-App "Blitztext" (MIT-Pflicht) und die beiden
        # Migrationskonstanten, die die Vorgängerversion übernehmen.
        erlaubt = ("blitztext-app", "Blitztext", "VORGAENGER_NAME =", "_ALTER_SERVICE_NAME =")
        treffer = [
            f"{pfad.relative_to(_QUELLEN)}:{nr}"
            for pfad in sorted(_QUELLEN.rglob("*.py"))
            for nr, zeile in enumerate(pfad.read_text(encoding="utf-8").splitlines(), 1)
            if ("schnacker" in zeile.lower() or "blitztext" in zeile.lower())
            and not any(a in zeile for a in erlaubt)
        ]
        self.assertEqual(treffer, [], "alter Name noch im Quellcode")


class VorgaengerOrdnerTest(unittest.TestCase):
    """Der Rename darf keine Nutzerdaten kosten: Einstellungen und die schon
    geladenen Whisper-Modelle liegen in Ordnern, die mit dem Paket hießen."""

    def setUp(self) -> None:
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.basis = Path(tmp.name)
        self.config = self.basis / "config" / "blablatext"
        self.data = self.basis / "share" / "blablatext"
        for name, wert in (("CONFIG_DIR", self.config), ("DATA_DIR", self.data)):
            p = mock.patch.object(settings_store, name, wert)
            p.start()
            self.addCleanup(p.stop)

    def _lege_alten_ordner_an(self, neu: Path, dateiname: str, inhalt: str) -> Path:
        alt = neu.with_name(settings_store.VORGAENGER_NAME)
        alt.mkdir(parents=True)
        (alt / dateiname).write_text(inhalt, encoding="utf-8")
        return alt

    def test_alte_einstellungen_werden_uebernommen(self) -> None:
        alt = self._lege_alten_ordner_an(self.config, "settings.json", '{"app": {}}')
        self.assertEqual(settings_store.migriere_vorgaenger_ordner(), [str(self.config)])
        self.assertEqual((self.config / "settings.json").read_text(encoding="utf-8"), '{"app": {}}')
        self.assertFalse(alt.exists())

    def test_geladene_modelle_werden_uebernommen(self) -> None:
        # Der teure Fall: mehrere GB Whisper-Modelle nicht neu herunterladen.
        self._lege_alten_ordner_an(self.data, "modell.bin", "x")
        settings_store.migriere_vorgaenger_ordner()
        self.assertTrue((self.data / "modell.bin").exists())

    def test_vorhandener_neuer_stand_wird_nicht_ueberschrieben(self) -> None:
        self._lege_alten_ordner_an(self.config, "settings.json", "alt")
        self.config.mkdir(parents=True)
        (self.config / "settings.json").write_text("neu", encoding="utf-8")

        self.assertEqual(settings_store.migriere_vorgaenger_ordner(), [])
        self.assertEqual((self.config / "settings.json").read_text(encoding="utf-8"), "neu")

    def test_ohne_alten_ordner_passiert_nichts(self) -> None:
        # Der Normalfall bei einer Neuinstallation — und beim zweiten Start.
        self.assertEqual(settings_store.migriere_vorgaenger_ordner(), [])
        self.assertFalse(self.config.exists())


class SchluesselbundUebernahmeTest(unittest.TestCase):
    """Der Schlüsselbund kann Einträge nicht umbenennen — also einmal umkopieren,
    sonst müsste jeder Nutzer seinen OpenAI-Key neu eintragen."""

    def setUp(self) -> None:
        keychain.invalidate_cache()
        self.addCleanup(keychain.invalidate_cache)

    def test_key_wird_aus_dem_alten_eintrag_uebernommen_und_neu_gespeichert(self) -> None:
        gespeichert = {}

        def get(service, key):
            return "sk-alt" if service == keychain._ALTER_SERVICE_NAME else None

        with mock.patch.object(keychain.keyring, "get_password", side_effect=get), \
             mock.patch.object(keychain.keyring, "set_password",
                               side_effect=lambda s, k, v: gespeichert.update({s: v})):
            self.assertEqual(keychain.load(), "sk-alt")

        self.assertEqual(gespeichert, {keychain._SERVICE_NAME: "sk-alt"})

    def test_neuer_eintrag_hat_vorrang_und_wird_nicht_neu_geschrieben(self) -> None:
        with mock.patch.object(keychain.keyring, "get_password", return_value="sk-neu") as get, \
             mock.patch.object(keychain.keyring, "set_password") as set_:
            self.assertEqual(keychain.load(), "sk-neu")
        get.assert_called_once_with(keychain._SERVICE_NAME, keychain._KEY_NAME)
        set_.assert_not_called()

    def test_ohne_beide_eintraege_bleibt_es_bei_none(self) -> None:
        with mock.patch.object(keychain.keyring, "get_password", return_value=None), \
             mock.patch.object(keychain.keyring, "set_password") as set_:
            self.assertIsNone(keychain.load())
        set_.assert_not_called()


if __name__ == "__main__":
    unittest.main()
