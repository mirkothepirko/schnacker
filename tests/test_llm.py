"""Tests für den OpenAI-Chat-Aufruf und den Prompt-Bau.

Es geht **kein** Netzverkehr raus: `requests.post` wird durch eine Attrappe
(englisch "fake") ersetzt, die eine vorbereitete Antwort zurückgibt. So testen
wir unsere Logik, nicht die von OpenAI.
"""

from __future__ import annotations

import unittest
from unittest import mock

from blablatext.models import TextImprovementSettings, TextTone
from blablatext.services import llm


class FakeResponse:
    """Minimaler Ersatz für ein requests.Response-Objekt."""

    def __init__(self, status_code: int = 200, payload=None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("keine JSON-Antwort")
        return self._payload


def antwort(inhalt: str) -> FakeResponse:
    return FakeResponse(payload={"choices": [{"message": {"content": inhalt}}]})


class CompleteTest(unittest.TestCase):
    """Der gemeinsame HTTP-Pfad aller Umschreibe-Funktionen."""

    def setUp(self) -> None:
        p = mock.patch.object(llm.keychain, "load", return_value="sk-test")
        p.start()
        self.addCleanup(p.stop)

    def test_ohne_api_key_klare_fehlermeldung(self) -> None:
        with mock.patch.object(llm.keychain, "load", return_value=None):
            with self.assertRaises(llm.LLMError) as ctx:
                llm.improve("Text", TextImprovementSettings())
        self.assertIn("API Key fehlt", str(ctx.exception))

    def test_antwort_wird_getrimmt_zurueckgegeben(self) -> None:
        with mock.patch.object(llm.requests, "post", return_value=antwort("  Fertig.\n")) as post:
            ergebnis = llm.improve("rohtext", TextImprovementSettings())
        self.assertEqual(ergebnis, "Fertig.")
        # Der Key gehört in den Authorization-Header, nicht in den Body.
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer sk-test")

    def test_nutzertext_und_systemprompt_landen_als_zwei_nachrichten(self) -> None:
        with mock.patch.object(llm.requests, "post", return_value=antwort("ok")) as post:
            llm.improve("mein diktat", TextImprovementSettings())
        messages = post.call_args.kwargs["json"]["messages"]
        self.assertEqual([m["role"] for m in messages], ["system", "user"])
        self.assertEqual(messages[1]["content"], "mein diktat")

    def test_fehlerstatus_wird_zu_lesbarem_fehler(self) -> None:
        fehler = FakeResponse(status_code=401, payload={"error": {"message": "Bad key"}})
        with mock.patch.object(llm.requests, "post", return_value=fehler):
            with self.assertRaises(llm.LLMError) as ctx:
                llm.improve("x", TextImprovementSettings())
        self.assertIn("Bad key", str(ctx.exception))

    def test_fehlerstatus_ohne_json_nennt_den_statuscode(self) -> None:
        with mock.patch.object(llm.requests, "post", return_value=FakeResponse(status_code=500)):
            with self.assertRaises(llm.LLMError) as ctx:
                llm.improve("x", TextImprovementSettings())
        self.assertIn("500", str(ctx.exception))

    def test_leere_antwort_ist_ein_fehler(self) -> None:
        with mock.patch.object(llm.requests, "post", return_value=antwort("   ")):
            with self.assertRaises(llm.LLMError):
                llm.improve("x", TextImprovementSettings())

    def test_kaputte_antwortstruktur_ist_ein_fehler(self) -> None:
        with mock.patch.object(llm.requests, "post", return_value=FakeResponse(payload={"a": 1})):
            with self.assertRaises(llm.LLMError):
                llm.improve("x", TextImprovementSettings())

    def test_netzwerkproblem_wird_zu_lesbarem_fehler(self) -> None:
        with mock.patch.object(llm.requests, "post",
                               side_effect=llm.requests.RequestException("kein Netz")):
            with self.assertRaises(llm.LLMError) as ctx:
                llm.improve("x", TextImprovementSettings())
        self.assertIn("Verbindungsproblem", str(ctx.exception))

    def test_mundart_uebersetzung_nutzt_das_grosse_modell(self) -> None:
        """Platt und Basel brauchen gpt-4o; das kleine Modell reicht dafür nicht."""
        with mock.patch.object(llm.requests, "post", return_value=antwort("moin")) as post:
            llm.dampf_ablassen("Guten Tag", "SYS-PLATT")
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["model"], "gpt-4o")
        self.assertEqual(body["temperature"], 0.4)
        self.assertEqual(body["messages"][0]["content"], "SYS-PLATT")

    def test_basel_verhaelt_sich_wie_platt(self) -> None:
        with mock.patch.object(llm.requests, "post", return_value=antwort("gruezi")) as post:
            llm.basel_deutsch("Guten Tag", "SYS-BASEL")
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["model"], "gpt-4o")
        self.assertEqual(body["temperature"], 0.4)
        self.assertEqual(body["messages"][0]["content"], "SYS-BASEL")

    def test_verbessern_nutzt_das_schnelle_modell(self) -> None:
        with mock.patch.object(llm.requests, "post", return_value=antwort("ok")) as post:
            llm.improve("x", TextImprovementSettings())
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["model"], "gpt-4o-mini")
        self.assertEqual(body["temperature"], 0.3)


class SystemPromptTest(unittest.TestCase):
    """Der zusammengebaute Lektorats-Prompt für Lektorat."""

    def test_eigener_prompt_ersetzt_den_standard(self) -> None:
        s = TextImprovementSettings(system_prompt="Nur Rechtschreibung.")
        self.assertEqual(llm._build_system_prompt(s), "Nur Rechtschreibung.")

    def test_eigener_prompt_bekommt_die_eigennamen_angehaengt(self) -> None:
        s = TextImprovementSettings(system_prompt="Nur Rechtschreibung.",
                                    custom_terms=["Flötotto"])
        prompt = llm._build_system_prompt(s)
        self.assertTrue(prompt.startswith("Nur Rechtschreibung."))
        self.assertIn("Flötotto", prompt)

    def test_standardprompt_enthaelt_den_tonfall(self) -> None:
        for tone, erwartet in [(TextTone.FORMAL, "formellen"),
                               (TextTone.NEUTRAL, "neutralen"),
                               (TextTone.CASUAL, "lockeren")]:
            with self.subTest(tone=tone):
                prompt = llm._build_system_prompt(TextImprovementSettings(tone=tone))
                self.assertIn(erwartet, prompt)

    def test_kontext_wird_angehaengt(self) -> None:
        s = TextImprovementSettings(context="E-Mails an Kunden")
        self.assertIn("Kontext: E-Mails an Kunden", llm._build_system_prompt(s))

    def test_mehrere_eigennamen_werden_mit_komma_aufgelistet(self) -> None:
        s = TextImprovementSettings(custom_terms=["Flötotto", "FLEX TABLE"])
        self.assertIn("Flötotto, FLEX TABLE", llm._build_system_prompt(s))

    def test_ohne_extras_bleibt_der_prompt_schlank(self) -> None:
        prompt = llm._build_system_prompt(TextImprovementSettings())
        self.assertIn("Lektor", prompt)
        self.assertNotIn("Kontext:", prompt)
        self.assertNotIn("Eigennamen", prompt)


if __name__ == "__main__":
    unittest.main()
