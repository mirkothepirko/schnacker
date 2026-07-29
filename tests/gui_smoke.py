"""Rauchtest der Oberfläche — läuft NICHT in der normalen Test-Suite.

Startet die echte App, baut jede der vier Seiten auf, schaltet alle
Menüleisten-Status durch, schickt einen Trigger über den Socket und beendet sich
selbst. Prüft damit die Verdrahtung, die die Unit-Tests nicht sehen (GTK-Widgets,
AppIndicator, Cairo-Icons, Socket).

Braucht einen Bildschirm — auf einem Server über Xvfb:

    xvfb-run -a env PYTHONPATH=. XDG_RUNTIME_DIR=/tmp python3 tests/gui_smoke.py

Auf einem echten Ubuntu-Desktop reicht:  python3 tests/gui_smoke.py
"""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk
from unittest import mock

from blitztext.app import SchnackerApp, socket_path, send_trigger, is_running
from blitztext.state import Page
from blitztext.models import WorkflowType

with mock.patch("blitztext.services.keychain.is_configured", return_value=True):
    app = SchnackerApp()
    app.start_socket_server()
    print("App gebaut, Socket lauscht:", is_running())

    for page in (Page.MAIN, Page.ONBOARDING, Page.SETTINGS):
        app.app_state.page = page
        app.popover.app_state.is_popover_shown = True
        app.popover._shown_page = None
        app.popover.rebuild()
        print(f"Seite {page.value:12s} aufgebaut, Kinder:",
              len(app.popover._content.get_children()))

    # Status-Animation durchschalten (rendert Icons + Tooltips)
    from blitztext.state import MenuBarStatus, StatusKind
    for kind in StatusKind:
        app._on_status_change(MenuBarStatus(kind, WorkflowType.TRANSCRIPTION))
    print("Alle Menüleisten-Status gerendert")

    # Einen Workflow per Socket-Trigger starten (ohne Mikrofon -> Fehlerphase)
    ergebnis = send_trigger("dampfAblassen")
    print("Trigger über Socket angenommen:", ergebnis)
    GLib.idle_add(lambda: (app.app_state.stop_current_workflow(), False)[1])

    # Workflow-Seite mit laufendem Workflow aufbauen (Wellenform!)
    app.app_state.page = Page.WORKFLOW
    app.popover._shown_page = None
    app.popover.rebuild()
    print("Seite workflow     aufgebaut")

    GLib.timeout_add(700, lambda: (app.quit(), False)[1])
    Gtk.main()
print("Sauber beendet. Socket entfernt:", not __import__("os").path.exists(socket_path()))
