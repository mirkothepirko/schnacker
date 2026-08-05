"""Globaler Tastatur-Listener für Halten/Loslassen — Linux-Pendant zu blablatexts
pynput-Listener (siehe dortiges `_on_key_press`/`_on_key_release`).

Warum nicht einfach ein GNOME-Systemkürzel (wie in shortcuts.py)?
GNOME/gsettings-Kürzel können nur "Taste drücken -> Befehl ausführen". Sie kennen
kein Halten/Loslassen. Für echtes Push-to-Talk (Strg+Super halten = aufnehmen,
loslassen = einfügen) und für Esc-Abbruch brauchen wir stattdessen rohe
Tastatur-Events direkt vom Kernel — das liefert `evdev` über /dev/input/eventX.

Rechte: Die Geräte gehören der Gruppe `input` (Standard-Ubuntu-udev-Regel).
`setup.sh` fügt den Benutzer dieser Gruppe bereits für ydotool hinzu — dieselbe
Mitgliedschaft erlaubt auch das *Lesen* der Tastatur-Events, es ist keine
zusätzliche Einrichtung nötig.

Wichtig: Wir öffnen die Geräte nur lesend und rufen NIE `grab()` auf. Das heißt,
die Tasten kommen ganz normal auch bei allen anderen Programmen an — wir hören
nur "im Hintergrund mit", wie ein zweiter Zuhörer, ohne etwas abzufangen.
"""

from __future__ import annotations

import sys
import threading
from typing import Callable

try:
    from evdev import InputDevice, ecodes, list_devices
except Exception:  # pragma: no cover - evdev evtl. nicht installiert
    InputDevice = None
    ecodes = None
    list_devices = None


CTRL_CODES = frozenset({"KEY_LEFTCTRL", "KEY_RIGHTCTRL"})
SUPER_CODES = frozenset({"KEY_LEFTMETA", "KEY_RIGHTMETA"})


class HeldKeysTracker:
    """Reine Zustandslogik (kein I/O) — hält fest, welche Modifier gerade gedrückt
    sind, und meldet Übergänge. Getrennt von der Geräte-Ein-/Ausgabe, damit sich
    die Logik ohne echte Tastatur testen lässt."""

    def __init__(self) -> None:
        self._held: set[str] = set()
        self._ptt_active = False

    def handle(self, key_name: str, value: int) -> str | None:
        """value: 1=drücken, 0=loslassen, 2=Auto-Wiederholung (wird ignoriert).
        Gibt "esc", "ptt_start", "ptt_stop" zurück, wenn dieses Event einen
        Übergang auslöst, sonst None."""
        if key_name == "KEY_ESC":
            return "esc" if value == 1 else None

        if key_name not in CTRL_CODES and key_name not in SUPER_CODES:
            return None
        if value == 2:
            return None

        if value == 1:
            self._held.add(key_name)
        else:
            self._held.discard(key_name)

        both_held = bool(self._held & CTRL_CODES) and bool(self._held & SUPER_CODES)
        if both_held and not self._ptt_active:
            self._ptt_active = True
            return "ptt_start"
        if not both_held and self._ptt_active:
            self._ptt_active = False
            return "ptt_stop"
        return None


def _is_keyboard(device: "InputDevice") -> bool:
    """Grober Filter: nur Geräte, die auch die Esc-Taste melden können — schließt
    z.B. reine Maus-/Lautstärke-Geräte aus, die ein paar EV_KEY-Codes melden."""
    caps = device.capabilities().get(ecodes.EV_KEY, [])
    return ecodes.KEY_ESC in caps


def _run_device_loop(path: str, tracker: HeldKeysTracker,
                      on_esc: Callable[[], None],
                      on_ptt_start: Callable[[], None],
                      on_ptt_stop: Callable[[], None],
                      lock: threading.Lock) -> None:
    try:
        device = InputDevice(path)
        if not _is_keyboard(device):
            return
    except OSError as exc:
        print(f"[global_hotkeys] Gerät {path} nicht lesbar: {exc}", file=sys.stderr, flush=True)
        return

    try:
        for event in device.read_loop():
            if event.type != ecodes.EV_KEY:
                continue
            key_name = ecodes.KEY[event.code] if event.code in ecodes.KEY else None
            if isinstance(key_name, list):  # manche Codes haben mehrere Namen
                key_name = key_name[0]
            if key_name is None:
                continue
            with lock:
                action = tracker.handle(key_name, event.value)
            if action == "esc":
                on_esc()
            elif action == "ptt_start":
                on_ptt_start()
            elif action == "ptt_stop":
                on_ptt_stop()
    except OSError:
        pass  # Gerät wurde entfernt (z.B. Bluetooth-Tastatur getrennt) -> Thread endet ruhig.


def start(on_esc: Callable[[], None], on_ptt_start: Callable[[], None],
          on_ptt_stop: Callable[[], None]) -> bool:
    """Startet für jede erkannte Tastatur einen Hintergrund-Thread. Gibt False
    zurück (und meldet das auf stderr), wenn evdev fehlt oder keine Tastatur
    gefunden wurde — Push-to-Talk/Esc bleiben dann einfach deaktiviert, der
    Rest der App läuft normal weiter (wie das pynput-Fallback in blablatext)."""
    if InputDevice is None:
        print("[global_hotkeys] evdev nicht verfügbar — Push-to-Talk/Esc-Abbruch deaktiviert.",
              file=sys.stderr, flush=True)
        return False

    try:
        paths = list_devices()
    except OSError as exc:
        print(f"[global_hotkeys] Konnte /dev/input nicht auflisten: {exc}", file=sys.stderr, flush=True)
        return False

    # Ein gemeinsamer Tracker + Lock über alle Tastaturen hinweg: wenn Strg auf der
    # einen und Super auf einer anderen (z.B. externen) Tastatur gedrückt wird,
    # soll Push-to-Talk trotzdem korrekt auslösen.
    tracker = HeldKeysTracker()
    lock = threading.Lock()

    started_any = False
    for path in paths:
        thread = threading.Thread(
            target=_run_device_loop,
            args=(path, tracker, on_esc, on_ptt_start, on_ptt_stop, lock),
            daemon=True,
        )
        thread.start()
        started_any = True

    if not started_any:
        print("[global_hotkeys] Keine Tastatur gefunden — Push-to-Talk/Esc-Abbruch deaktiviert.",
              file=sys.stderr, flush=True)
    return started_any
