"""Tests für den Workflow-Ablauf — das Herzstück der App.

Aufnahme, Transkription und LLM werden durch Attrappen ersetzt. Getestet wird die
**Reihenfolge**: Aufnahme -> (zu kurz? abbrechen) -> transkribieren -> ggf.
umschreiben -> Phase `done` + Ausgabe. Genau diese Kette fassen wir beim
Refactoring an, deshalb wird sie hier festgenagelt.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest import mock

from blablatext.models import (
    DampfAblassenSettings,
    EmojiTextSettings,
    Phase,
    TextImprovementSettings,
    TranscriptionBackend,
    WorkflowType,
)
from blablatext.workflows import base, llm_workflow
from blablatext.workflows.transcription import TranscriptionWorkflow


class FakeRecorder:
    """Ersatz für den echten AudioRecorder — schreibt nichts, nimmt nichts auf."""

    def __init__(self, dauer: float = 3.0) -> None:
        self.is_recording = False
        self.recording_path: Path | None = None
        self.error_message: str | None = None
        self.audio_level = 0.0
        self.last_recording_duration = dauer
        self.discarded = False
        self._dauer = dauer

    def start_recording(self) -> None:
        self.is_recording = True

    def stop_recording(self) -> None:
        self.is_recording = False
        # Eine echte (leere) Datei, damit `unlink` im Workflow etwas zu tun hat.
        tmp = NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        self.recording_path = Path(tmp.name)
        self.last_recording_duration = self._dauer

    def discard_recording(self) -> None:
        self.discarded = True
        if self.recording_path:
            self.recording_path.unlink(missing_ok=True)
            self.recording_path = None


class WorkflowTestBase(unittest.TestCase):
    """Gemeinsame Hilfen: Recorder-Attrappe einsetzen, Phasen mitschreiben."""

    def baue(self, workflow, dauer: float = 3.0):
        workflow._recorder = FakeRecorder(dauer)
        self.phasen = []
        self.ausgaben = []
        workflow.on_phase_change = lambda p: self.phasen.append((p.phase, p.text))
        workflow.on_output = self.ausgaben.append
        return workflow

    def durchlaufen(self, workflow) -> None:
        """start + stop, und auf den Verarbeitungs-Thread warten."""
        workflow.start()
        workflow.stop()
        if workflow._thread is not None:
            workflow._thread.join(timeout=5)

    @property
    def letzte_phase(self):
        return self.phasen[-1]


class BaseWorkflowTest(WorkflowTestBase):

    def test_start_setzt_phase_auf_running(self) -> None:
        wf = self.baue(TranscriptionWorkflow())
        wf.start()
        self.assertEqual(self.letzte_phase, (Phase.RUNNING, "Aufnahme läuft ..."))
        self.assertTrue(wf.is_recording)

    def test_aufnahmefehler_wird_zur_fehlerphase(self) -> None:
        wf = self.baue(TranscriptionWorkflow())
        wf._recorder.start_recording = lambda: setattr(
            wf._recorder, "error_message", "Kein Mikrofon")
        wf.start()
        self.assertEqual(self.letzte_phase, (Phase.ERROR, "Kein Mikrofon"))

    def test_zu_kurze_aufnahme_wird_verworfen_und_nicht_verschickt(self) -> None:
        wf = self.baue(TranscriptionWorkflow(), dauer=0.1)
        with mock.patch("blablatext.services.transcription.transcribe") as t:
            self.durchlaufen(wf)
        t.assert_not_called()
        self.assertEqual(self.letzte_phase, (Phase.ERROR, "Keine Aufnahme erkannt."))
        self.assertTrue(wf._recorder.discarded)

    def test_grenze_der_mindestlaenge(self) -> None:
        """0.29 s wird verworfen, 0.3 s geht durch — hier lauern <=/<-Vertipper."""
        for dauer, soll_verschickt_werden in [(0.29, False), (0.3, True)]:
            with self.subTest(dauer=dauer):
                wf = self.baue(TranscriptionWorkflow(), dauer=dauer)
                with mock.patch("blablatext.services.transcription.transcribe",
                                return_value="Hi") as t:
                    self.durchlaufen(wf)
                self.assertEqual(t.called, soll_verschickt_werden)

    def test_stop_ohne_laufende_aufnahme_geht_auf_idle(self) -> None:
        wf = self.baue(TranscriptionWorkflow())
        wf.stop()
        self.assertEqual(self.letzte_phase, (Phase.IDLE, ""))

    def test_reset_verwirft_die_aufnahme(self) -> None:
        wf = self.baue(TranscriptionWorkflow())
        wf.start()
        wf.reset()
        self.assertEqual(self.letzte_phase, (Phase.IDLE, ""))
        self.assertTrue(wf._recorder.discarded)

    def test_eigennamen_werden_bei_sehr_kurzer_aufnahme_nicht_mitgeschickt(self) -> None:
        """Unter 0.9 s liefert Whisper mit Prompt eher Halluzinationen — wie im Original."""
        wf = self.baue(TranscriptionWorkflow(custom_terms=["Flötotto"]), dauer=0.5)
        with mock.patch("blablatext.services.transcription.transcribe",
                        return_value="kurz") as t:
            self.durchlaufen(wf)
        self.assertEqual(t.call_args.kwargs["custom_terms"], [])

    def test_eigennamen_werden_ab_09_sekunden_mitgeschickt(self) -> None:
        wf = self.baue(TranscriptionWorkflow(custom_terms=["Flötotto"]), dauer=0.9)
        with mock.patch("blablatext.services.transcription.transcribe",
                        return_value="Ein etwas laengerer Satz hier") as t:
            self.durchlaufen(wf)
        self.assertEqual(t.call_args.kwargs["custom_terms"], ["Flötotto"])

    def test_audiodatei_wird_nach_der_verarbeitung_geloescht(self) -> None:
        wf = self.baue(TranscriptionWorkflow())
        with mock.patch("blablatext.services.transcription.transcribe", return_value="Hallo"):
            wf.start()
            wf.stop()
            pfad = wf._recorder.recording_path
            wf._thread.join(timeout=5)
        self.assertFalse(pfad.exists(), "Die Aufnahme muss nach der Verarbeitung weg sein")

    def test_fehler_in_der_verarbeitung_wird_zur_fehlerphase(self) -> None:
        wf = self.baue(TranscriptionWorkflow())
        with mock.patch("blablatext.services.transcription.transcribe",
                        side_effect=RuntimeError("API kaputt")):
            self.durchlaufen(wf)
        self.assertEqual(self.letzte_phase, (Phase.ERROR, "API kaputt"))
        self.assertEqual(self.ausgaben, [])

    def test_abbruch_waehrend_der_verarbeitung_meldet_keinen_fehler(self) -> None:
        wf = self.baue(TranscriptionWorkflow())

        def transkribieren_und_abbrechen(*_a, **_k):
            wf._cancelled = True
            return "Text der niemanden mehr interessiert"

        with mock.patch("blablatext.services.transcription.transcribe",
                        side_effect=transkribieren_und_abbrechen):
            self.durchlaufen(wf)
        self.assertEqual(self.ausgaben, [])
        self.assertNotEqual(self.letzte_phase[0], Phase.ERROR)


class TranscriptionWorkflowTest(WorkflowTestBase):

    def test_online_transkription_gibt_text_aus(self) -> None:
        wf = self.baue(TranscriptionWorkflow())
        with mock.patch("blablatext.services.transcription.transcribe",
                        return_value="  Hallo Welt  "):
            self.durchlaufen(wf)
        self.assertEqual(self.ausgaben, ["Hallo Welt"])
        self.assertEqual(self.letzte_phase, (Phase.DONE, "Hallo Welt"))

    def test_lokaler_modus_nutzt_das_lokale_modell(self) -> None:
        wf = self.baue(TranscriptionWorkflow(backend=TranscriptionBackend.LOCAL,
                                             local_model_name="small"))
        with mock.patch("blablatext.services.local_transcription.transcribe",
                        return_value="lokal erkannt") as lokal, \
             mock.patch("blablatext.services.transcription.transcribe") as online:
            self.durchlaufen(wf)
        online.assert_not_called()
        lokal.assert_called_once()
        self.assertEqual(self.ausgaben, ["lokal erkannt"])

    def test_lokaler_modus_zeigt_eigenen_statustext(self) -> None:
        wf = self.baue(TranscriptionWorkflow(backend=TranscriptionBackend.LOCAL))
        with mock.patch("blablatext.services.local_transcription.transcribe", return_value="x y z"):
            self.durchlaufen(wf)
        texte = [t for _p, t in self.phasen]
        self.assertIn("Wird lokal transkribiert ...", texte)

    def test_whisper_artefakt_wird_abgefangen(self) -> None:
        # 0.4 s Aufnahme, aber ein langer Text zurück -> Halluzination.
        wf = self.baue(TranscriptionWorkflow(), dauer=0.4)
        with mock.patch("blablatext.services.transcription.transcribe",
                        return_value="Vielen Dank fuers Zuschauen und bis zum naechsten Mal"):
            self.durchlaufen(wf)
        self.assertEqual(self.letzte_phase, (Phase.ERROR, "Keine Aufnahme erkannt."))
        self.assertEqual(self.ausgaben, [])


class LLMWorkflowsTest(WorkflowTestBase):
    """Die drei Workflows mit zweitem Schritt (Verbessern / Platt / Basel)."""

    def test_verbessern_transkribiert_dann_lektoriert(self) -> None:
        wf = self.baue(llm_workflow.text_improvement(settings=TextImprovementSettings()))
        with mock.patch("blablatext.services.transcription.transcribe", return_value="roh text"), \
             mock.patch("blablatext.services.llm.improve", return_value="Roher Text.") as verbessern:
            self.durchlaufen(wf)
        self.assertEqual(verbessern.call_args.args[0], "roh text")
        self.assertEqual(self.ausgaben, ["Roher Text."])
        self.assertIn("Text wird verbessert ...", [t for _p, t in self.phasen])

    def test_verbessern_uebernimmt_eigennamen_aus_den_einstellungen(self) -> None:
        s = TextImprovementSettings(custom_terms=["Flötotto"])
        wf = self.baue(llm_workflow.text_improvement(settings=s))
        self.assertEqual(wf.custom_terms, ["Flötotto"])

    def test_platt_transkribiert_dann_uebersetzt(self) -> None:
        wf = self.baue(llm_workflow.dampf_ablassen(settings=DampfAblassenSettings()))
        with mock.patch("blablatext.services.transcription.transcribe", return_value="Guten Tag"), \
             mock.patch("blablatext.services.llm.dampf_ablassen", return_value="Moin") as platt:
            self.durchlaufen(wf)
        self.assertEqual(platt.call_args.args[0], "Guten Tag")
        self.assertEqual(platt.call_args.args[1], DampfAblassenSettings().system_prompt)
        self.assertEqual(self.ausgaben, ["Moin"])
        self.assertIn("Wird ins Platt übersetzt ...", [t for _p, t in self.phasen])

    def test_basel_transkribiert_dann_uebersetzt(self) -> None:
        wf = self.baue(llm_workflow.basel_deutsch(settings=EmojiTextSettings()))
        with mock.patch("blablatext.services.transcription.transcribe", return_value="Guten Tag"), \
             mock.patch("blablatext.services.llm.basel_deutsch", return_value="Grüezi") as basel:
            self.durchlaufen(wf)
        self.assertEqual(basel.call_args.args[0], "Guten Tag")
        self.assertEqual(basel.call_args.args[1], EmojiTextSettings().system_prompt)
        self.assertEqual(self.ausgaben, ["Grüezi"])
        self.assertIn("Wird ins Baseldütsch übersetzt ...", [t for _p, t in self.phasen])

    def test_platt_meldet_das_keine_aufnahme_signal_des_modells(self) -> None:
        """Antwortet das Modell mit dem Signalwort, ist es keine echte Ausgabe."""
        wf = self.baue(llm_workflow.dampf_ablassen(settings=DampfAblassenSettings()))
        with mock.patch("blablatext.services.transcription.transcribe", return_value="Guten Tag"), \
             mock.patch("blablatext.services.llm.dampf_ablassen",
                        return_value="KEINE_AUFNAHME_ERKANNT"):
            self.durchlaufen(wf)
        self.assertEqual(self.letzte_phase, (Phase.ERROR, "Keine Aufnahme erkannt."))
        self.assertEqual(self.ausgaben, [])

    def test_basel_meldet_das_keine_aufnahme_signal_des_modells(self) -> None:
        wf = self.baue(llm_workflow.basel_deutsch(settings=EmojiTextSettings()))
        with mock.patch("blablatext.services.transcription.transcribe", return_value="Guten Tag"), \
             mock.patch("blablatext.services.llm.basel_deutsch",
                        return_value="  KEINE_AUFNAHME_ERKANNT  "):
            self.durchlaufen(wf)
        self.assertEqual(self.letzte_phase, (Phase.ERROR, "Keine Aufnahme erkannt."))

    def test_verbessern_meldet_das_keine_aufnahme_signal_ebenfalls(self) -> None:
        """Neu und bewusst: vorher prüften nur Platt/Basel dieses Signalwort.

        Ohne die Prüfung würde bei Lektorat im Fehlerfall wörtlich
        "KEINE_AUFNAHME_ERKANNT" in den Text eingefügt.
        """
        wf = self.baue(llm_workflow.text_improvement(settings=TextImprovementSettings()))
        with mock.patch("blablatext.services.transcription.transcribe", return_value="Guten Tag"), \
             mock.patch("blablatext.services.llm.improve",
                        return_value="KEINE_AUFNAHME_ERKANNT"):
            self.durchlaufen(wf)
        self.assertEqual(self.letzte_phase, (Phase.ERROR, "Keine Aufnahme erkannt."))
        self.assertEqual(self.ausgaben, [])

    def test_llm_workflows_ueberspringen_das_llm_bei_artefakt(self) -> None:
        wf = self.baue(llm_workflow.dampf_ablassen(settings=DampfAblassenSettings()), dauer=0.4)
        with mock.patch("blablatext.services.transcription.transcribe",
                        return_value="Vielen Dank fuers Zuschauen und bis zum naechsten Mal"), \
             mock.patch("blablatext.services.llm.dampf_ablassen") as platt:
            self.durchlaufen(wf)
        platt.assert_not_called()
        self.assertEqual(self.letzte_phase, (Phase.ERROR, "Keine Aufnahme erkannt."))

    def test_jeder_workflow_kennt_seinen_typ(self) -> None:
        faelle = [
            (TranscriptionWorkflow(), WorkflowType.TRANSCRIPTION),
            (llm_workflow.text_improvement(settings=TextImprovementSettings()),
             WorkflowType.TEXT_IMPROVER),
            (llm_workflow.dampf_ablassen(settings=DampfAblassenSettings()),
             WorkflowType.DAMPF_ABLASSEN),
            (llm_workflow.basel_deutsch(settings=EmojiTextSettings()), WorkflowType.EMOJI_TEXT),
        ]
        for wf, erwartet in faelle:
            with self.subTest(workflow=type(wf).__name__):
                self.assertEqual(wf.type, erwartet)


class CancelledExceptionTest(unittest.TestCase):

    def test_workflow_cancelled_ist_eine_ausnahme(self) -> None:
        self.assertTrue(issubclass(base.WorkflowCancelled, Exception))


if __name__ == "__main__":
    unittest.main()
