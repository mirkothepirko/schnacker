"""Tests für die Online-Transkription — vor allem für den Eigennamen-Prompt.

„Flötotto" wird von Whisper ohne Hinweis regelmäßig falsch erkannt, deshalb geht
der Firmenname als eingebauter Begriff *immer* mit — unabhängig von den
nutzerdefinierten Eigennamen. Dieses Verhalten ist schon zweimal verloren gegangen
(beim Rebranding und weil der Commit nie in `main` landete), darum steht es jetzt
im Test.

Kein Netzverkehr: `requests.post` und der Schlüsselbund sind durch Attrappen ersetzt.
"""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from blitztext.services import transcription


class _FakeResponse:
    status_code = 200
    text = "Ein transkribierter Satz."


class EigennamenPromptTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.audio = Path(self._tmp.name) / "audio.wav"
        self.audio.write_bytes(b"RIFF____WAVE")
        self.addCleanup(self._tmp.cleanup)

    def _transcribe(self, **kwargs) -> dict:
        """Ruft transcribe() auf und gibt die gesendeten Formularfelder zurück."""
        with mock.patch.object(transcription.keychain, "load", return_value="sk-test"), \
             mock.patch.object(transcription.requests, "post",
                               return_value=_FakeResponse()) as post:
            transcription.transcribe(self.audio, **kwargs)
        return post.call_args.kwargs["data"]

    def test_floetotto_geht_auch_ohne_eigene_begriffe_mit(self):
        data = self._transcribe()
        self.assertIn("Flötotto", data["prompt"])

    def test_floetotto_steht_vor_den_eigenen_begriffen(self):
        data = self._transcribe(custom_terms=["Plattenkonfigurator"])
        self.assertEqual(data["prompt"],
                         "Eigennamen und Begriffe: Flötotto, Plattenkonfigurator")

    def test_doppelt_genannter_begriff_erscheint_nur_einmal(self):
        # Trägt der Nutzer "Flötotto" selbst ein, darf es nicht zweimal im Prompt stehen.
        data = self._transcribe(custom_terms=["Flötotto", "FLEX TABLE"])
        self.assertEqual(data["prompt"], "Eigennamen und Begriffe: Flötotto, FLEX TABLE")

    def test_sprache_wird_mitgeschickt_wenn_gesetzt(self):
        data = self._transcribe(language="de")
        self.assertEqual(data["language"], "de")

    def test_leere_sprache_wird_weggelassen(self):
        data = self._transcribe(language="   ")
        self.assertNotIn("language", data)

    def test_fehlender_api_key_meldet_lesbaren_fehler(self):
        with mock.patch.object(transcription.keychain, "load", return_value=""):
            with self.assertRaises(transcription.TranscriptionError) as ctx:
                transcription.transcribe(self.audio)
        self.assertIn("API Key", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
