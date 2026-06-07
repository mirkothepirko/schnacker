# Blitztext für Ubuntu

Sprache in Text verwandeln — direkt aus der Menüleiste. Diese App ist eine
**funktionsgleiche Neuentwicklung** der macOS-App
[Blitztext](https://github.com/cmagnussen/blitztext-app) für **Ubuntu / GNOME / Wayland**.

Sie bietet dieselben vier Workflows wie das Original:

| Workflow | Was es tut | Modell |
|---|---|---|
| **Blitztext** | Sprache aufnehmen und transkribieren | OpenAI Whisper **oder** lokal (offline) |
| **Blitztext+** | Transkript zu sauberem Text lektorieren | OpenAI GPT‑4o‑mini |
| **Blitztext $%&!** | Frust-Nachricht ruhig & sachlich umformulieren | OpenAI GPT‑4o |
| **Blitztext :)** | Passende Emojis in den Text streuen | OpenAI GPT‑4o‑mini |

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
3. **Auto-Einfügen (ydotool)** einrichten: eine udev-Regel für den uinput-Zugriff,
   dich zur Gruppe `input` hinzufügen und den Hintergrund-Dienst `ydotoold` starten.
4. Einen **Programmstarter** im Anwendungsmenü anlegen.

> **Wichtig:** Wenn du beim ersten Mal zur Gruppe `input` hinzugefügt wirst, musst du
> dich **einmal ab- und wieder anmelden**, damit das automatische Einfügen funktioniert.
> Vorher landet der Text trotzdem in der Zwischenablage (du fügst dann mit `Strg+V` ein).

---

## Starten

```bash
.venv/bin/python -m blitztext
```

…oder einfach **„Blitztext"** im Anwendungsmenü suchen und anklicken.

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
3. Tab **„Anpassen"**: Schreibstil, eigene Anweisungen, Eigennamen, Emoji-Dichte und der
   **Sichere Lokale Modus** (offline-Transkription) lassen sich hier einstellen.

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
  | `Strg+Alt+1` | Blitztext (Diktat) |
  | `Strg+Alt+2` | Blitztext+ |
  | `Strg+Alt+3` | Blitztext $%&! |
  | `Strg+Alt+4` | Blitztext :) |

### Sicherer Lokaler Modus (offline)

Im Tab „Anpassen" (oder direkt im Hauptmenü über den Schalter) lässt sich der lokale
Modus einschalten. Dann wird **nichts an OpenAI gesendet** — die Transkription läuft mit
**faster‑whisper** komplett auf deinem Rechner. Das Modell (Standard: „Whisper Small")
wird beim ersten Mal heruntergeladen. Hinweis: Die drei KI-Workflows (+, $%&!, :)) sind
im lokalen Modus pausiert, weil sie OpenAI brauchen — genau wie im Original.

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

- **Tastenkürzel** sind GNOME-Systemkürzel (`Strg+Alt+1`…) im **„Drücken"-Modus**
  (1× drücken = Start, nochmal = Stopp). Das „Halten = aufnehmen" des Originals ist unter
  Wayland nicht möglich; die Einstellung bleibt sichtbar, verhält sich aber wie „Drücken".
- **Auto-Einfügen** funktioniert nur bei Start über ein Tastenkürzel. Beim Start über das
  Fenster geht der Text in die Zwischenablage (Wayland erlaubt kein zuverlässiges
  Zurückspringen ins vorherige Fenster).

Alles andere — die vier Workflows, dieselben KI-Prompts/Modelle, die deutschen Texte und
die Bedienlogik — ist 1:1 nachgebaut.

---

## Fehlerbehebung

- **Auto-Einfügen tut nichts:** einmal ab-/anmelden (Gruppe `input`). Testen, ob ydotool
  auf `/dev/uinput` darf: `ydotool key ctrl` (Exit-Code 0 = ok). Auto-Einfügen klappt nur,
  wenn der Workflow **per Tastenkürzel** (nicht über das Fenster) gestartet wurde.
- **„ydotool fehlt":** `./setup.sh` erneut ausführen.
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

## Lizenz

Das Original steht unter der MIT-Lizenz. Diese Nachbildung folgt demselben Geist:
ein Lern- und Experimentierprojekt, ohne Gewähr.
