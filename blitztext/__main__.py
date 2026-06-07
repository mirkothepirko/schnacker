"""Einstiegspunkt — gestartet mit `python -m blitztext`.

Aufrufvarianten:
    python -m blitztext                      App starten (Menüleisten-Symbol)
    python -m blitztext --trigger <workflow> Workflow starten/stoppen (für GNOME-Kürzel)
    python -m blitztext --install-shortcuts  GNOME-Kürzel Super+1..4 einrichten
"""

from __future__ import annotations

import argparse
import sys

from .models import WorkflowType


def main() -> None:
    parser = argparse.ArgumentParser(prog="blitztext", description="Blitztext für Ubuntu")
    parser.add_argument("--trigger", metavar="WORKFLOW",
                        help="Workflow per Tastenkürzel starten/stoppen "
                             "(transcription, textImprover, dampfAblassen, emojiText).")
    parser.add_argument("--install-shortcuts", action="store_true",
                        help="GNOME-Tastenkürzel Super+1 bis Super+4 einrichten.")
    args = parser.parse_args()

    if args.install_shortcuts:
        from .shortcuts import install_gnome_shortcuts
        print(install_gnome_shortcuts())
        return

    if args.trigger:
        # Prüfen, dass es ein bekannter Workflow ist.
        try:
            WorkflowType(args.trigger)
        except ValueError:
            valid = ", ".join(t.value for t in WorkflowType)
            print(f"Unbekannter Workflow '{args.trigger}'. Gültig: {valid}", file=sys.stderr)
            sys.exit(1)

        from .app import send_trigger
        if not send_trigger(args.trigger):
            print("Blitztext läuft nicht. Bitte zuerst die App starten.", file=sys.stderr)
            sys.exit(1)
        return

    # Normale App starten — aber nur eine Instanz gleichzeitig.
    from .app import BlitztextApp, is_running
    if is_running():
        print("Blitztext läuft bereits (siehe Menüleisten-Symbol).")
        return
    BlitztextApp().run()


if __name__ == "__main__":
    main()
