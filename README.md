# Schnacker für Ubuntu

Sprache in Text verwandeln — direkt aus der Menüleiste. Diese App ist eine
**eigenständige Linux-Neuentwicklung**, inspiriert von der macOS-App
[Blitztext](https://github.com/cmagnussen/blitztext-app), für **Ubuntu / GNOME / Wayland**.

Sie bietet vier Workflows — die ersten beiden wie im Original, die letzten beiden sind
**eigene Anpassungen** (Mundart-Übersetzung statt der Originalfunktionen):

| Workflow | Was es tut | Modell |
|---|---|---|
| **Schnacker** | Sprache aufnehmen und transkribieren | OpenAI Whisper **oder** lokal (offline) |
| **Schnacker+** | Transkript zu sauberem Text lektorieren | OpenAI GPT‑4o‑mini |
| **Schnacker Platt** | Hochdeutsch nach Plattdeutsch übersetzen | OpenAI GPT‑4o |
| **Schnacker Basel** | Hochdeutsch nach Baseldütsch übersetzen | OpenAI GPT‑4o |

> Warum eine Neuentwicklung statt Portierung? Das Original ist in Swift/SwiftUI mit
> Apples WhisperKit geschrieben — das läuft ausschließlich auf macOS. Unter Linux
> bauen wir dasselbe mit **Python + GTK**, **faster‑whisper** (statt WhisperKit),
> **ydotool** (statt der macOS-Einfügefunktion) und dem **GNOME-Schlüsselbund** (statt Keychain).

---

## Voraussetzungen

- Ubuntu 24.04 (GNOME, Wayland) — getestet auf genau dieser Umgebung
- Ein Mikrofon
- Für die Online-Workflows: ein eigener **OpenAI API Key** (https://platform.openai.com)
- Für rein lokale Transkription: nichts weiter — das Modell wird beim ersten Mal geladen

---

## Installation

Im Projektordner einmal das Einrichtungs-Skript ausführen:

```bash
./setup.sh
```

Das Skript macht der Reihe nach (und fragt dabei **einmal nach deinem sudo-Passwort**):

1. **System-Pakete** installieren (GTK, Menüleisten-Symbol, Mikrofon-Zugriff,
   Zwischenablage, ydotool).
2. Eine **Python-Umgebung** (`.venv`) anlegen und die Python-Pakete installieren
   (`requests`, `sounddevice`, `keyring`, `faster-whisper`).
3. **Auto-Einfügen (ydotool)** einrichten: eine udev-Regel für den uinput-Zugriff und
   dich zur Gruppe `input` hinzufügen. (Nur bei neueren ydotool-Versionen wird zusätzlich
   der Dienst `ydotoold` gestartet — das Ubuntu-24.04-Paket ydotool 0.1.8 braucht keinen.)
4. Einen **Programmstarter** im Anwendungsmenü anlegen.

> **Wichtig:** Wenn du beim ersten Mal zur Gruppe `input` hinzugefügt wirst, musst du
> dich **einmal ab- und wieder anmelden**, damit das automatische Einfügen funktioniert.
> Vorher landet der Text trotzdem in der Zwischenablage (du fügst dann mit `Strg+V` ein).

---

## Starten

```bash
.venv/bin/python -m blitztext
```

…oder einfach **„Schnacker"** im Anwendungsmenü suchen und anklicken.

Es erscheint ein **Symbol oben rechts in der Leiste**. Ein Klick darauf öffnet das Menü
mit den Workflows, den Einstellungen und „Beenden".

> **Kein Symbol sichtbar?** GNOME zeigt solche Symbole nur mit der Erweiterung
> *„AppIndicator and KStatusNotifierItem Support"*. Diese ist auf Ubuntu normalerweise
> aktiv (`ubuntu-appindicators@ubuntu.com`). Prüfen/aktivieren kannst du sie mit der
> App **„Erweiterungen"** (`gnome-extensions-app`).

---

## Einrichten in der App

1. Klicke auf das Menüleisten-Symbol → **Einstellungen …**
2. Tab **„Zugang"**:
   - **OpenAI API Key** eintragen und auf **Speichern** klicken. Der Key wird sicher im
     **GNOME-Schlüsselbund** abgelegt (nicht im Klartext).
   - **GNOME-Kürzel einrichten** anklicken → legt `Strg+Alt+1` bis `Strg+Alt+4` für die vier
     Workflows an.
3. Tab **„Anpassen"**: Schreibstil, eigene Anweisungen, Eigennamen, die Mundart-Prompts
   (Platt/Basel) und der **Sichere Lokale Modus** (offline-Transkription) lassen sich hier einstellen.

---

## Benutzen

- **Über das Menü:** Symbol anklicken → einen Workflow wählen → es öffnet sich das
  Fenster mit der Wellenform. Sprechen, dann auf den Stopp-Knopf klicken. Das Ergebnis
  landet in der **Zwischenablage** (mit `Strg+V` einfügen).
- **Über Tastenkürzel (empfohlen, wie das Original):** `Strg+Alt+1` drücken startet die
  Aufnahme im Hintergrund, **nochmal `Strg+Alt+1`** stoppt sie — der fertige Text wird dann
  **automatisch dort eingefügt**, wo dein Cursor steht (per ydotool).

  | Kürzel | Workflow |
  |---|---|
  | `Strg+Alt+1` | Schnacker (Diktat) |
  | `Strg+Alt+2` | Schnacker+ |
  | `Strg+Alt+3` | Schnacker Platt |
  | `Strg+Alt+4` | Schnacker Basel |

- **Push-to-Talk:** `Strg+Super` (Windows-Taste) **halten** startet die Aufnahme,
  **loslassen** stoppt sie und fügt automatisch ein. `Esc` verwirft eine laufende
  Aufnahme, ohne sie einzufügen.

  Welcher Workflow auf `Strg+Super` liegt, wählst du im Tab „Anpassen" unter
  **Tastenkürzel** — alle vier Workflows stehen zur Wahl, dazu **„Aus"**. „Aus" schaltet
  Push-to-Talk und den Esc-Abbruch komplett ab: dann startet Schnacker den
  Tastatur-Listener gar nicht und liest keine Tastendrücke mit. Die Umschaltung auf
  bzw. von „Aus" wirkt erst nach einem Neustart der App.

### Sicherer Lokaler Modus (offline)

Im Tab „Anpassen" (oder direkt im Hauptmenü über den Schalter) lässt sich der lokale
Modus einschalten. Dann wird **nichts an OpenAI gesendet** — die Transkription läuft mit
**faster‑whisper** komplett auf deinem Rechner. Das Modell (Standard: „Whisper Small")
wird beim ersten Mal heruntergeladen. Hinweis: Die drei KI-Workflows (Schnacker+, Platt,
Basel) sind im lokalen Modus pausiert, weil sie OpenAI brauchen — genau wie im Original.

---

## Sicherheit & Datenschutz

- **API Key:** liegt verschlüsselt im GNOME-Schlüsselbund, niemals im Code oder in einer
  Klartext-Datei.
- **Datenfluss (Online-Modus):** Audio geht direkt an die OpenAI-Whisper-API, Text an die
  OpenAI-Chat-API. Es gibt **keinen** Zwischen-Server.
- **Lokaler Modus:** Es verlässt nichts deinen Rechner.
- **ydotool / uinput:** ydotool kann Tastatureingaben simulieren — das ist mächtig.
  Deshalb richtet `setup.sh` den Zugriff bewusst über eine **udev-Regel + Gruppe `input`**
  ein, statt den Dienst dauerhaft als root laufen zu lassen.

---

## Unterschiede zum Original (Wayland-bedingt)

Wayland sperrt aus Sicherheitsgründen einige Dinge, die das macOS-Original nutzt. Daher:

- **Die vier Profil-Kürzel** (`Strg+Alt+1`…) sind GNOME-Systemkürzel im
  **„Drücken"-Modus** (1× drücken = Start, nochmal = Stopp). GNOME-Kürzel kennen kein
  Halten/Loslassen — sie können nur „Taste gedrückt → Befehl ausführen".
- **Push-to-Talk** (`Strg+Super` halten) und der **Esc-Abbruch** laufen deshalb über
  einen eigenen, rohen Tastatur-Listener (`evdev`, siehe
  `blitztext/services/global_hotkeys.py`) statt über GNOME-Kürzel — das ist unter
  Wayland der einzige Weg, Halten und Loslassen zu unterscheiden.

  Der Listener öffnet die Tastaturen **nur lesend** und ruft nie `grab()` auf: die
  Tasten kommen ganz normal auch bei allen anderen Programmen an, er hört nur mit.
  Das heißt aber auch, dass Schnacker währenddessen alle Tastendrücke sieht. Wer das
  nicht möchte, stellt `Strg+Super` auf **„Aus"** — dann wird der Listener nicht
  gestartet. Nichts davon verlässt den Rechner.
- **Auto-Einfügen** funktioniert nur bei Start über ein Tastenkürzel oder Push-to-Talk.
  Beim Start über das Fenster geht der Text in die Zwischenablage (Wayland erlaubt kein
  zuverlässiges Zurückspringen ins vorherige Fenster).

Die Bedienlogik, die deutschen Texte und die ersten beiden Workflows (Diktat, Schnacker+)
folgen dem Original. **Schnacker Platt** und **Schnacker Basel** sind eigene Anpassungen und
ersetzen die Originalfunktionen „$%&!" (Frust entschärfen) und „:)" (Emojis einstreuen).

---

## Tests

Die Test-Suite braucht **keine** zusätzlichen Pakete (nur Pythons eingebautes
`unittest`) und geht nicht ins Netz — OpenAI, Mikrofon und Schlüsselbund werden
durch Attrappen ersetzt.

```bash
python3 -m unittest discover -s tests -t .        # alle Tests
python3 -m unittest tests.test_workflows -v       # nur ein Bereich, ausführlich
```

Zusätzlich gibt es einen Rauchtest der Oberfläche, der die echte App startet,
jede Seite aufbaut und sich selbst beendet (braucht einen Bildschirm):

```bash
python3 tests/gui_smoke.py
```

---

## Fehlerbehebung

- **Auto-Einfügen tut nichts:** einmal ab-/anmelden (Gruppe `input`). Testen, ob ydotool
  auf `/dev/uinput` darf: `ydotool key ctrl` (Exit-Code 0 = ok). Auto-Einfügen klappt nur,
  wenn der Workflow **per Tastenkürzel** (nicht über das Fenster) gestartet wurde.
- **„ydotool fehlt":** `./setup.sh` erneut ausführen.
- **Push-to-Talk (`Strg+Super`) oder Esc-Abbruch reagieren nicht:** meist fehlt die
  Gruppe `input` — nach `./setup.sh` einmal ab- und wieder anmelden (dieselbe
  Mitgliedschaft wie für ydotool). Prüfen mit `groups | grep input`. Startest du
  Schnacker im Terminal (`.venv/bin/python -m blitztext`), nennt eine Zeile
  `[global_hotkeys] …` den Grund. Die Funktion schaltet sich dann nur selbst ab, der
  Rest der App läuft normal weiter. Und: steht die Auswahl auf „Aus", ist es Absicht.
- **Kein Mikrofon:** in den Ubuntu-Einstellungen unter *Ton → Eingang* das richtige Gerät
  wählen.
- **Tastenkürzel kollidiert:** `Strg+Alt+1` etc. ggf. in *Einstellungen → Tastatur* anpassen.

---

## Projektstruktur (spiegelt das Original)

```
blitztext/
  models.py             Typen & Einstellungen        (~ WorkflowProtocol.swift)
  state.py              Zentraler Zustand            (~ AppState.swift)
  app.py                Tray, Fenster, Socket        (~ BlitztextMacApp.swift)
  __main__.py           Einstieg + CLI
  shortcuts.py          GNOME-Tastenkürzel
  services/             Aufnahme, OpenAI, lokal, Schlüsselbund, Einfügen
  workflows/            Die vier Workflows + Basis
  ui/                   Popover, Einstellungen, Wellenform, Tray-Icon
setup.sh                Einrichtungs-Skript
```

---

## Lizenz & Herkunft

Das Original [Blitztext](https://github.com/cmagnussen/blitztext-app) steht unter der
**MIT-Lizenz**; der Copyright-Hinweis bleibt in der Datei [LICENSE](LICENSE) erhalten. Diese
Linux-Neuentwicklung übernimmt Teile davon und steht ebenfalls unter MIT — ein Lern- und
Experimentierprojekt, ohne Gewähr.

**Hinweis zur Marke:** Die MIT-Lizenz gewährt **nicht** die Rechte am Namen, Logo oder der
Optik des Originals (siehe dessen `TRADEMARKS.md`). Wer einen Fork als eigene App oder
eigenen Dienst veröffentlicht, soll einen **eigenen Namen und eigenes Branding** verwenden.
