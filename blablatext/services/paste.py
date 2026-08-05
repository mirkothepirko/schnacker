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


def _simulate_ctrl_v() -> bool:
    """Drückt Strg+V via ydotool. True, wenn es geklappt hat.

    Scheitert es (nicht installiert / keine Rechte auf /dev/uinput), ist das kein
    Drama: der Text liegt in der Zwischenablage, der Nutzer drückt selbst Strg+V.
    """
    if not shutil.which("ydotool"):
        return False

    # ydotool 0.1.8-Syntax: Tastennamen mit '+'. 'ctrl+v' drückt die Tasten
    # zusammen und lässt sie wieder los. (Die 1.x-Keycode-Syntax versteht 0.1.8 nicht.)
    try:
        result = subprocess.run(["ydotool", "key", "ctrl+v"],
                                capture_output=True, text=True, timeout=5)
    except (subprocess.SubprocessError, OSError):
        return False
    return result.returncode == 0


def paste_at_cursor(text: str) -> bool:
    """Kopiert den Text und versucht, ihn per Strg+V automatisch einzufügen.
    True, wenn das automatische Einfügen geklappt hat.

    Der Text bleibt absichtlich in der Zwischenablage — als Fallback, falls das
    automatische Einfügen blockiert ist (genau wie im Original)."""
    copy_to_clipboard(text)

    # Kurze Pause, damit das Zielfenster den Fokus sicher hat, bevor wir tippen.
    time.sleep(0.12)

    return _simulate_ctrl_v()
