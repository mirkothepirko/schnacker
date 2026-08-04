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

from blitztext.app import BlablatextApp, socket_path, send_trigger, is_running
from blitztext.state import Page
from blitztext.models import WorkflowType

with mock.patch("blitztext.services.keychain.is_configured", return_value=True):
    app = BlablatextApp()
    app.start_socket_server()
    print("App gebaut, Socket lauscht:", is_running())

    for page in (Page.MAIN, Page.ONBOARDING, Page.SETTINGS):
        app.app_state.page = page
        app.popover.app_state.is_popover_shown = True
        app.popover._shown_page = None
        app.popover.rebuild()
        print(f"Seite {page.value:12s} aufgebaut, Kinder:",
              len(app.popover._content.get_children()))

    # Auswahllisten: klappt eine auf, darf der Fokusverlust das Fenster NICHT
    # schließen. Nur mit echtem GTK prüfbar — vorher klappte hier das ganze
    # Einstellungsfenster zu, sobald man den Schreibstil auswählen wollte.
    app.app_state.page = Page.SETTINGS
    app.popover._shown_page = None
    app.popover.rebuild()

    # Die Liste klappt nur auf einem sichtbaren Fenster auf — also erst zeigen und
    # GTK die anstehenden Ereignisse abarbeiten lassen. Geöffnet wird über das
    # Aktions-Signal "popup" (derselbe Weg wie per Tastatur); die GTK-Warnung
    # "no trigger event for menu popup" ist dabei normal, weil kein echter Klick
    # dahintersteckt.
    app.popover.show_all()
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)

    for name, combo in (("Schreibstil", app.popover._settings_view._tone_combo),
                        ("Lokales Modell", app.popover._settings_view._model_combo),
                        ("Strg+Super", app.popover._settings_view._ptt_combo)):
        combo.emit("popup")
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        offen = app.popover._dropdown_offen
        # Fokusverlust simulieren, während die Liste offen ist.
        app.popover._on_focus_out(app.popover, None)
        noch_da = app.app_state.is_popover_shown
        combo.emit("popdown")
        zu = not app.popover._dropdown_offen
        print(f"Liste {name:15s} Merker gesetzt: {offen}, Fenster bleibt offen: "
              f"{noch_da}, Merker zurückgesetzt: {zu}")
        assert offen and noch_da and zu, f"Auswahlliste {name} schließt das Fenster"

    # Gegenprobe: ohne offene Liste muss der Fokusverlust weiterhin schließen.
    app.popover.app_state.is_popover_shown = True
    app.popover._on_focus_out(app.popover, None)
    assert not app.app_state.is_popover_shown, "Fokusverlust schließt das Fenster nicht mehr"
    print("Gegenprobe: Fokusverlust ohne offene Liste schließt weiterhin")

    # Push-to-Talk: "Aus" darf den rohen Tastatur-Listener gar nicht starten —
    # das ist der Sinn der Option (die App liest dann keine Tastendrücke mit).
    from blitztext.models import PushToTalkTarget
    from blitztext.services import global_hotkeys

    for ziel, soll_starten in ((PushToTalkTarget.OFF, False),
                               (PushToTalkTarget.TRANSCRIPTION, True)):
        app.app_state.settings.app.push_to_talk_target = ziel
        with mock.patch.object(global_hotkeys, "start", return_value=True) as start:
            app.start_global_hotkeys()
        gestartet = start.called
        print(f"Listener bei {ziel.value:14s} gestartet: {gestartet}")
        assert gestartet is soll_starten, f"Listener-Start bei {ziel.value} falsch"

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
