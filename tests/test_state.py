"""Tests für den zentralen App-Zustand (state.py).

Hier hängt die Frage "welcher Workflow ist gerade nutzbar?" — die Antwort hängt
vom API-Key und vom sicheren lokalen Modus ab. Diese Kombinationen sind mit dem
Auge kaum zu prüfen, deshalb steht hier eine kleine Wahrheitstabelle.

GTK wird nur importiert, nicht gestartet: wir rufen keine Fenster-Funktionen auf.
"""

from __future__ import annotations

import unittest
from unittest import mock

from blitztext import models
from blitztext.models import LaunchSource, WorkflowType
from blitztext.services import settings_store


def zustand(*, key_vorhanden: bool = True, lokal_an: bool = False,
            modell_installiert: bool = False):
    """Baut einen AppState mit gefälschtem Schlüsselbund und Modell-Status.

    Die Attrappen bleiben absichtlich **nach** dem Bauen aktiv (kein `with`),
    weil `is_workflow_available` sie bei jedem Aufruf erneut befragt. Aufgeräumt
    wird im `tearDown` des jeweiligen Tests über `mock.patch.stopall()`.
    """
    from blitztext import state as state_modul

    bundle = settings_store.SettingsBundle()
    bundle.app.secure_local_mode_enabled = lokal_an
    for p in (
        mock.patch.object(settings_store, "load", return_value=bundle),
        mock.patch.object(state_modul.keychain, "is_configured", return_value=key_vorhanden),
        mock.patch.object(state_modul.local, "is_model_installed",
                          return_value=modell_installiert),
        mock.patch.object(state_modul.local, "installed_models",
                          return_value=["small"] if modell_installiert else []),
    ):
        p.start()
    return state_modul.AppState()


class VerfuegbarkeitTest(unittest.TestCase):
    """Wahrheitstabelle: Wann ist ein Workflow anklickbar?"""

    def tearDown(self) -> None:
        mock.patch.stopall()

    def test_online_mit_key_alles_verfuegbar(self) -> None:
        st = zustand(key_vorhanden=True, lokal_an=False)
        for t in WorkflowType.main_menu_cases():
            with self.subTest(workflow=t):
                self.assertTrue(st.is_workflow_available(t))

    def test_online_ohne_key_nichts_verfuegbar(self) -> None:
        st = zustand(key_vorhanden=False, lokal_an=False)
        for t in WorkflowType.main_menu_cases():
            with self.subTest(workflow=t):
                self.assertFalse(st.is_workflow_available(t))

    def test_lokaler_modus_nur_diktat_und_nur_mit_modell(self) -> None:
        st = zustand(key_vorhanden=True, lokal_an=True, modell_installiert=True)
        self.assertTrue(st.is_workflow_available(WorkflowType.TRANSCRIPTION))
        # Die KI-Workflows brauchen das Netz -> im lokalen Modus gesperrt.
        for t in (WorkflowType.TEXT_IMPROVER, WorkflowType.DAMPF_ABLASSEN,
                  WorkflowType.EMOJI_TEXT):
            with self.subTest(workflow=t):
                self.assertFalse(st.is_workflow_available(t))

    def test_lokaler_modus_ohne_modell_sperrt_auch_das_diktat(self) -> None:
        st = zustand(key_vorhanden=True, lokal_an=True, modell_installiert=False)
        self.assertFalse(st.is_workflow_available(WorkflowType.TRANSCRIPTION))

    def test_is_configured_gilt_auch_ohne_key_mit_lokalem_modell(self) -> None:
        st = zustand(key_vorhanden=False, modell_installiert=True)
        self.assertTrue(st.is_configured)

    def test_ohne_alles_ist_nichts_konfiguriert(self) -> None:
        st = zustand(key_vorhanden=False, modell_installiert=False)
        self.assertFalse(st.is_configured)
        self.assertTrue(st.should_show_onboarding)

    def test_onboarding_verschwindet_nach_dem_ersten_mal(self) -> None:
        st = zustand(key_vorhanden=False, modell_installiert=False)
        st.settings.app.has_seen_onboarding = True
        self.assertFalse(st.should_show_onboarding)


class AnzeigenamenTest(unittest.TestCase):

    def tearDown(self) -> None:
        mock.patch.stopall()

    def test_ohne_eigenen_namen_gilt_der_standardname(self) -> None:
        st = zustand()
        self.assertEqual(st.display_name(WorkflowType.TRANSCRIPTION), "Schnacker")
        self.assertEqual(st.display_name(WorkflowType.TEXT_IMPROVER), "Schnacker+")

    def test_eigener_name_gewinnt(self) -> None:
        st = zustand()
        st.settings.text_improvement.custom_name = "Mein Lektor"
        self.assertEqual(st.display_name(WorkflowType.TEXT_IMPROVER), "Mein Lektor")

    def test_eigener_name_aus_leerzeichen_wird_ignoriert(self) -> None:
        st = zustand()
        st.settings.dampf_ablassen.custom_name = "   "
        self.assertEqual(st.display_name(WorkflowType.DAMPF_ABLASSEN), "Schnacker Platt")

    def test_untertitel_zeigt_den_aktiven_transkriptions_weg(self) -> None:
        online = zustand(lokal_an=False)
        self.assertIn("Online", online.workflow_subtitle(WorkflowType.TRANSCRIPTION))
        mock.patch.stopall()

        lokal = zustand(lokal_an=True, modell_installiert=True)
        self.assertIn("Lokal", lokal.workflow_subtitle(WorkflowType.TRANSCRIPTION))

    def test_untertitel_warnt_bei_fehlendem_lokalem_modell(self) -> None:
        st = zustand(lokal_an=True, modell_installiert=False)
        self.assertIn("fehlt", st.workflow_subtitle(WorkflowType.TRANSCRIPTION))

    def test_ki_workflows_melden_pause_im_lokalen_modus(self) -> None:
        st = zustand(lokal_an=True, modell_installiert=True)
        self.assertIn("pausiert", st.workflow_subtitle(WorkflowType.TEXT_IMPROVER))


class WorkflowStartTest(unittest.TestCase):

    def tearDown(self) -> None:
        mock.patch.stopall()

    def test_start_ohne_key_fuehrt_in_die_einstellungen(self) -> None:
        from blitztext.state import Page

        st = zustand(key_vorhanden=False)
        st.start_workflow(WorkflowType.TEXT_IMPROVER, LaunchSource.MANUAL)
        self.assertIsNone(st.active_workflow)
        self.assertEqual(st.page, Page.SETTINGS)

    def test_start_per_hotkey_ohne_key_bleibt_stumm(self) -> None:
        """Kein Fenster aufreißen, wenn der Nutzer nur ein Kürzel gedrückt hat."""
        from blitztext.state import Page

        st = zustand(key_vorhanden=False)
        st.page = Page.MAIN
        st.start_workflow(WorkflowType.TEXT_IMPROVER, LaunchSource.HOTKEY_BACKGROUND)
        self.assertIsNone(st.active_workflow)
        self.assertEqual(st.page, Page.MAIN)

    def test_start_legt_den_passenden_workflow_an(self) -> None:
        st = zustand()
        for t in WorkflowType.main_menu_cases():
            with self.subTest(workflow=t):
                with mock.patch("blitztext.workflows.base.Workflow.start"):
                    st.start_workflow(t, LaunchSource.MANUAL)
                self.assertIsNotNone(st.active_workflow)
                self.assertEqual(st.active_workflow.type, t)

    def test_manueller_start_zeigt_die_workflow_seite(self) -> None:
        from blitztext.state import Page

        st = zustand()
        with mock.patch("blitztext.workflows.base.Workflow.start"):
            st.start_workflow(WorkflowType.TRANSCRIPTION, LaunchSource.MANUAL)
        self.assertEqual(st.page, Page.WORKFLOW)

    def test_hotkey_start_bleibt_auf_der_hauptseite(self) -> None:
        from blitztext.state import Page

        st = zustand()
        with mock.patch("blitztext.workflows.base.Workflow.start"):
            st.start_workflow(WorkflowType.TRANSCRIPTION, LaunchSource.HOTKEY_BACKGROUND)
        self.assertEqual(st.page, Page.MAIN)

    def test_neuer_start_stoppt_den_laufenden_workflow(self) -> None:
        st = zustand()
        with mock.patch("blitztext.workflows.base.Workflow.start"):
            st.start_workflow(WorkflowType.TRANSCRIPTION, LaunchSource.MANUAL)
            erster = st.active_workflow
            with mock.patch.object(erster, "stop") as stoppen:
                st.start_workflow(WorkflowType.DAMPF_ABLASSEN, LaunchSource.MANUAL)
        stoppen.assert_called_once()

    def test_lokaler_modus_waehlt_das_lokale_backend(self) -> None:
        st = zustand(lokal_an=True, modell_installiert=True)
        with mock.patch("blitztext.workflows.base.Workflow.start"):
            st.start_workflow(WorkflowType.TRANSCRIPTION, LaunchSource.MANUAL)
        self.assertEqual(st.active_workflow.backend, models.TranscriptionBackend.LOCAL)

    def test_online_modus_waehlt_das_remote_backend(self) -> None:
        st = zustand(lokal_an=False)
        with mock.patch("blitztext.workflows.base.Workflow.start"):
            st.start_workflow(WorkflowType.TRANSCRIPTION, LaunchSource.MANUAL)
        self.assertEqual(st.active_workflow.backend, models.TranscriptionBackend.REMOTE)

    def test_eigennamen_wandern_in_jeden_workflow(self) -> None:
        st = zustand()
        st.settings.text_improvement.custom_terms = ["Flötotto"]
        for t in WorkflowType.main_menu_cases():
            with self.subTest(workflow=t):
                with mock.patch("blitztext.workflows.base.Workflow.start"):
                    st.start_workflow(t, LaunchSource.MANUAL)
                self.assertEqual(st.active_workflow.custom_terms, ["Flötotto"])


class AusgabeTest(unittest.TestCase):
    """Kürzel-Start fügt automatisch ein, Fenster-Start kopiert nur."""

    def tearDown(self) -> None:
        mock.patch.stopall()

    def test_hotkey_start_fuegt_automatisch_ein(self) -> None:
        from blitztext import state as state_modul

        st = zustand()
        st._active_launch_source = LaunchSource.HOTKEY_BACKGROUND
        with mock.patch.object(state_modul.paste, "paste_at_cursor") as einfuegen, \
             mock.patch.object(state_modul.paste, "copy_to_clipboard") as kopieren, \
             mock.patch.object(state_modul.GLib, "idle_add"):
            st._handle_output("Text", mock.Mock())
        einfuegen.assert_called_once_with("Text")
        kopieren.assert_not_called()

    def test_manueller_start_kopiert_nur(self) -> None:
        from blitztext import state as state_modul

        st = zustand()
        st._active_launch_source = LaunchSource.MANUAL
        with mock.patch.object(state_modul.paste, "paste_at_cursor") as einfuegen, \
             mock.patch.object(state_modul.paste, "copy_to_clipboard") as kopieren, \
             mock.patch.object(state_modul.GLib, "idle_add"):
            st._handle_output("Text", mock.Mock())
        kopieren.assert_called_once_with("Text")
        einfuegen.assert_not_called()


class MenuBarStatusTest(unittest.TestCase):

    def test_gleiche_werte_sind_gleich(self) -> None:
        from blitztext.state import MenuBarStatus, StatusKind

        a = MenuBarStatus(StatusKind.RECORDING, WorkflowType.TRANSCRIPTION)
        b = MenuBarStatus(StatusKind.RECORDING, WorkflowType.TRANSCRIPTION)
        c = MenuBarStatus(StatusKind.IDLE)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_idle_hat_keinen_workflow(self) -> None:
        from blitztext.state import MenuBarStatus, StatusKind

        self.assertIsNone(MenuBarStatus(StatusKind.IDLE).workflow_type)


class ModelsTest(unittest.TestCase):

    def test_hauptmenue_zeigt_vier_workflows(self) -> None:
        self.assertEqual(len(WorkflowType.main_menu_cases()), 4)

    def test_jeder_workflow_hat_namen_und_untertitel(self) -> None:
        for t in WorkflowType:
            with self.subTest(workflow=t):
                self.assertTrue(t.display_name)
                self.assertTrue(t.subtitle)

    def test_workflow_werte_sind_die_gespeicherten_namen(self) -> None:
        """Diese Texte stehen in den GNOME-Kürzeln — sie dürfen sich nicht ändern."""
        self.assertEqual(
            [t.value for t in WorkflowType.main_menu_cases()],
            ["transcription", "textImprover", "dampfAblassen", "emojiText"])

    def test_nur_manueller_start_zeigt_die_workflow_seite(self) -> None:
        self.assertTrue(LaunchSource.MANUAL.presents_workflow_page)
        self.assertFalse(LaunchSource.HOTKEY_BACKGROUND.presents_workflow_page)


if __name__ == "__main__":
    unittest.main()
