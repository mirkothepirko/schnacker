"""Zwischenablage & Auto-Einfügen — Ersatz für die Paste-Logik aus AppState.swift
und AccessibilityPermissionService.swift.

Unter Wayland kann eine App Tastendrücke nicht einfach simulieren (Sicherheits-
sperre). Zwei Bausteine lösen das:
    * `wl-copy`  legt Text in die Zwischenablage (wie NSPasteboard).
    * `ydotool`  simuliert Strg+V auf Kernel-Ebene (/dev/uinput) — das einzige
                 Verfahren, das auch unter GNOME/Mutter zuverlässig funktioniert.

Hinweis zur ydotool-Version: Ubuntu (24.04) liefert ydotool 0.1.8. Diese Version
braucht KEINEN Hintergrund-Daemon (ydotoold) — sie greift direkt auf /dev/uinput zu
(dafür sorgt setup.sh über die udev-Regel + Gruppe `input`). Außerdem nutzt 0.1.8 die
Syntax mit Tastennamen (`ydotool key ctrl+v`), nicht die Keycode-Syntax der 1.x-Reihe.

Klappt ydotool nicht (nicht installiert / keine Rechte), bleibt der Text in der
Zwischenablage und der Nutzer fügt selbst mit Strg+V ein — wie das Fallback im Original.
"""

from __future__ import annotations

import shutil
import subprocess
import time


class PasteResult:
    """Ergebnis eines Einfüge-Versuchs."""

    def __init__(self, copied: bool, pasted: bool, error: str | None = None) -> None:
        self.copied = copied    # liegt der Text in der Zwischenablage?
        self.pasted = pasted    # wurde automatisch eingefügt?
        self.error = error


def copy_to_clipboard(text: str) -> bool:
    """Legt Text in die Wayland-Zwischenablage. Gibt True bei Erfolg zurück."""
    if not shutil.which("wl-copy"):
        return False
    try:
        subprocess.run(["wl-copy", "--", text], check=True, timeout=5)
        return True
    except (subprocess.SubprocessError, OSError):
        return False


def is_auto_paste_available() -> bool:
    """True, wenn ydotool grundsätzlich aufrufbar ist (Programm vorhanden)."""
    return shutil.which("ydotool") is not None


def _simulate_ctrl_v() -> tuple[bool, str | None]:
    """Drückt Strg+V via ydotool. Rückgabe: (erfolgreich, Fehlertext)."""
    if not shutil.which("ydotool"):
        return False, "ydotool ist nicht installiert."

    # ydotool 0.1.8-Syntax: Tastennamen mit '+'. 'ctrl+v' drückt die Tasten
    # zusammen und lässt sie wieder los. (Die 1.x-Keycode-Syntax versteht 0.1.8 nicht.)
    cmd = ["ydotool", "key", "ctrl+v"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except (subprocess.SubprocessError, OSError) as exc:
        return False, f"ydotool-Fehler: {exc}"

    if result.returncode != 0:
        detail = result.stderr.strip() or "unbekannter Fehler"
        # Häufigster Fall: keine Rechte auf /dev/uinput (Gruppe 'input' fehlt).
        return False, f"Auto-Einfügen nicht möglich ({detail})."
    return True, None


def paste_at_cursor(text: str) -> PasteResult:
    """Kopiert den Text und versucht, ihn per Strg+V automatisch einzufügen.

    Der Text bleibt absichtlich in der Zwischenablage — als Fallback, falls das
    automatische Einfügen blockiert ist (genau wie im Original)."""
    copied = copy_to_clipboard(text)

    # Kurze Pause, damit das Zielfenster den Fokus sicher hat, bevor wir tippen.
    time.sleep(0.12)

    pasted, error = _simulate_ctrl_v()
    return PasteResult(copied=copied, pasted=pasted, error=error)
