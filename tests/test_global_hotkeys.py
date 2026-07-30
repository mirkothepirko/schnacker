"""Tests für den Tastatur-Zustandsautomaten hinter Push-to-Talk.

`HeldKeysTracker` ist absichtlich frei von Ein-/Ausgabe: er bekommt Tastennamen und
Werte hineingereicht und meldet Übergänge. Deshalb ist er hier ohne echte Tastatur
und ohne virtuelles Eingabegerät prüfbar — das Öffnen der Geräte und das
Ereignis-Lesen (`_run_device_loop`, `start`) bleibt ungetestet und muss von Hand
gegengeprüft werden.

Werte der evdev-Ereignisse: 1 = drücken, 0 = loslassen, 2 = Auto-Wiederholung.
"""
import unittest

from blitztext.services.global_hotkeys import HeldKeysTracker

DRUECKEN, LOSLASSEN, WIEDERHOLUNG = 1, 0, 2


class PushToTalkTest(unittest.TestCase):
    def setUp(self):
        self.t = HeldKeysTracker()

    def test_strg_allein_loest_nichts_aus(self):
        self.assertIsNone(self.t.handle("KEY_LEFTCTRL", DRUECKEN))

    def test_super_allein_loest_nichts_aus(self):
        self.assertIsNone(self.t.handle("KEY_LEFTMETA", DRUECKEN))

    def test_strg_dann_super_startet(self):
        self.t.handle("KEY_LEFTCTRL", DRUECKEN)
        self.assertEqual(self.t.handle("KEY_LEFTMETA", DRUECKEN), "ptt_start")

    def test_umgekehrte_reihenfolge_startet_genauso(self):
        self.t.handle("KEY_LEFTMETA", DRUECKEN)
        self.assertEqual(self.t.handle("KEY_LEFTCTRL", DRUECKEN), "ptt_start")

    def test_eine_taste_loslassen_stoppt(self):
        self.t.handle("KEY_LEFTCTRL", DRUECKEN)
        self.t.handle("KEY_LEFTMETA", DRUECKEN)
        self.assertEqual(self.t.handle("KEY_LEFTCTRL", LOSLASSEN), "ptt_stop")

    def test_zweites_loslassen_stoppt_nicht_noch_einmal(self):
        # Sonst würde stop_push_to_talk() zweimal laufen.
        self.t.handle("KEY_LEFTCTRL", DRUECKEN)
        self.t.handle("KEY_LEFTMETA", DRUECKEN)
        self.t.handle("KEY_LEFTCTRL", LOSLASSEN)
        self.assertIsNone(self.t.handle("KEY_LEFTMETA", LOSLASSEN))

    def test_auto_wiederholung_startet_nicht_erneut(self):
        # Hält man die Tasten, feuert der Kernel laufend Wert 2. Ohne diese Abfrage
        # würde die Aufnahme immer wieder neu gestartet.
        self.t.handle("KEY_LEFTCTRL", DRUECKEN)
        self.t.handle("KEY_LEFTMETA", DRUECKEN)
        self.assertIsNone(self.t.handle("KEY_LEFTCTRL", WIEDERHOLUNG))
        self.assertIsNone(self.t.handle("KEY_LEFTMETA", WIEDERHOLUNG))

    def test_rechte_tasten_zaehlen_ebenso(self):
        self.t.handle("KEY_RIGHTCTRL", DRUECKEN)
        self.assertEqual(self.t.handle("KEY_RIGHTMETA", DRUECKEN), "ptt_start")

    def test_gemischt_links_rechts_zaehlt_auch(self):
        # Strg links, Super rechts — oder auf zwei verschiedenen Tastaturen.
        self.t.handle("KEY_LEFTCTRL", DRUECKEN)
        self.assertEqual(self.t.handle("KEY_RIGHTMETA", DRUECKEN), "ptt_start")

    def test_zweites_strg_dazu_startet_nicht_erneut(self):
        self.t.handle("KEY_LEFTCTRL", DRUECKEN)
        self.t.handle("KEY_LEFTMETA", DRUECKEN)
        self.assertIsNone(self.t.handle("KEY_RIGHTCTRL", DRUECKEN))

    def test_ein_strg_loslassen_stoppt_nicht_wenn_das_andere_noch_haelt(self):
        self.t.handle("KEY_LEFTCTRL", DRUECKEN)
        self.t.handle("KEY_RIGHTCTRL", DRUECKEN)
        self.t.handle("KEY_LEFTMETA", DRUECKEN)
        self.assertIsNone(self.t.handle("KEY_LEFTCTRL", LOSLASSEN))

    def test_zweiter_durchgang_startet_wieder(self):
        for _ in range(2):
            self.t.handle("KEY_LEFTCTRL", DRUECKEN)
            self.assertEqual(self.t.handle("KEY_LEFTMETA", DRUECKEN), "ptt_start")
            self.assertEqual(self.t.handle("KEY_LEFTMETA", LOSLASSEN), "ptt_stop")
            self.t.handle("KEY_LEFTCTRL", LOSLASSEN)

    def test_andere_tasten_werden_ignoriert(self):
        # Wichtig: der Listener liest ALLES mit, darf aber nur auf die Kürzel reagieren.
        for taste in ("KEY_A", "KEY_LEFTSHIFT", "KEY_F5", "KEY_SPACE"):
            self.assertIsNone(self.t.handle(taste, DRUECKEN), taste)


class EscTest(unittest.TestCase):
    def setUp(self):
        self.t = HeldKeysTracker()

    def test_esc_druecken_meldet_abbruch(self):
        self.assertEqual(self.t.handle("KEY_ESC", DRUECKEN), "esc")

    def test_esc_loslassen_meldet_nichts(self):
        self.assertIsNone(self.t.handle("KEY_ESC", LOSLASSEN))

    def test_esc_waehrend_push_to_talk_beendet_ptt_nicht_versehentlich(self):
        # Esc verwirft die Aufnahme; das Loslassen der Modifier meldet danach
        # trotzdem noch ptt_stop — stop_push_to_talk() prüft dann, dass gar nichts
        # mehr aufnimmt, und tut nichts.
        self.t.handle("KEY_LEFTCTRL", DRUECKEN)
        self.t.handle("KEY_LEFTMETA", DRUECKEN)
        self.assertEqual(self.t.handle("KEY_ESC", DRUECKEN), "esc")
        self.assertEqual(self.t.handle("KEY_LEFTMETA", LOSLASSEN), "ptt_stop")


if __name__ == "__main__":
    unittest.main()
