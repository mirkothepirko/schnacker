"""Tests für die Schließ-Entscheidung des Popover-Fensters.

Das Einstellungsfenster ist kein echtes GTK-Popover, sondern ein randloses
eigenes Fenster, das sich bei Fokusverlust selbst schließt. Genau diese Regel
war der Fehler: eine Gtk.ComboBoxText klappt ihre Liste in einem *eigenen*
Fenster auf und zieht dabei den Fokus zu sich — für GTK ein ganz normaler
Fokusverlust, also flog das Einstellungsfenster mitsamt der Liste zu.

Getestet wird deshalb die Entscheidung allein, ohne GTK-Fenster: soll bei
Fokusverlust geschlossen werden, ja oder nein?
"""
import unittest

from blablatext.models import Phase
from blablatext.ui.popover import soll_bei_fokusverlust_schliessen


class _FakePhase:
    """Minimaler Ersatz für PhaseState — nur die zwei gelesenen Felder."""

    def __init__(self, phase: Phase, is_active: bool) -> None:
        self.phase = phase
        self.is_active = is_active


class _FakeWorkflow:
    def __init__(self, phase: Phase, is_active: bool = True) -> None:
        self.phase = _FakePhase(phase, is_active)


class SchliessEntscheidungTest(unittest.TestCase):
    def test_ohne_workflow_und_ohne_dropdown_wird_geschlossen(self):
        # Der Normalfall: Klick neben das Fenster -> zu, wie ein echtes Popover.
        self.assertTrue(soll_bei_fokusverlust_schliessen(None, dropdown_offen=False))

    def test_offenes_dropdown_verhindert_das_schliessen(self):
        # Der eigentliche Fehler: die Liste der ComboBox nimmt den Fokus.
        self.assertFalse(soll_bei_fokusverlust_schliessen(None, dropdown_offen=True))

    def test_laufender_workflow_verhindert_das_schliessen(self):
        # Bestehendes Verhalten: während der Aufnahme nicht schließen, sonst bricht sie ab.
        wf = _FakeWorkflow(Phase.RUNNING)
        self.assertFalse(soll_bei_fokusverlust_schliessen(wf, dropdown_offen=False))

    def test_fertiger_workflow_verhindert_das_schliessen_nicht(self):
        wf = _FakeWorkflow(Phase.DONE)
        self.assertTrue(soll_bei_fokusverlust_schliessen(wf, dropdown_offen=False))

    def test_inaktiver_workflow_in_phase_running_verhindert_nichts(self):
        # is_active ist das ausschlaggebende Feld — nicht die Phase allein.
        wf = _FakeWorkflow(Phase.RUNNING, is_active=False)
        self.assertTrue(soll_bei_fokusverlust_schliessen(wf, dropdown_offen=False))

    def test_dropdown_gewinnt_auch_gegen_einen_fertigen_workflow(self):
        wf = _FakeWorkflow(Phase.DONE)
        self.assertFalse(soll_bei_fokusverlust_schliessen(wf, dropdown_offen=True))


if __name__ == "__main__":
    unittest.main()
