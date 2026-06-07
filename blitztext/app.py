"""App-Verbindungsstück — portiert aus BlitztextMacApp.swift / AppDelegate.

Bringt alles zusammen:
    * AppIndicator (Menüleisten-Symbol + Menü)        ~ NSStatusItem
    * Popover-Fenster                                  ~ NSPopover
    * Status-Animation des Symbols                     ~ MenuBarStatusController
    * Einzel-Instanz + Tastenkürzel-Empfang über Socket ~ Hotkey-Empfang
    * GNOME-Tastenkürzel einrichten (gsettings)        ~ HotkeyService

Threading-Hinweis: Eingehende Tastenkürzel-Befehle kommen über einen Hintergrund-
Thread herein; wir verarbeiten sie mit GLib.idle_add wieder im Haupt-Thread.
"""

from __future__ import annotations

import os
import socket
import threading

import gi

gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator
except (ValueError, ImportError):  # Fallback auf die ältere Variante
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3 as AppIndicator

from gi.repository import GLib, Gtk  # noqa: E402

from . import shortcuts
from .models import LaunchSource, WorkflowType
from .state import AppState, MenuBarStatus, StatusKind
from .ui.popover import PopoverWindow
from .ui.tray_icon import TrayIconRenderer


def socket_path() -> str:
    """Pfad des Steuer-Sockets (für Einzel-Instanz + Tastenkürzel-Befehle)."""
    runtime = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return f"{runtime}/blitztext.sock"


# MARK: - Trigger-Client (für `--trigger`) ------------------------------------


def send_trigger(workflow_name: str) -> bool:
    """Schickt einen Workflow-Auslöser an die laufende App. True bei Erfolg."""
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(2)
        client.connect(socket_path())
        client.sendall(workflow_name.encode("utf-8"))
        client.close()
        return True
    except OSError:
        return False


def is_running() -> bool:
    """True, wenn bereits eine Blitztext-Instanz auf dem Socket lauscht."""
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(1)
        client.connect(socket_path())
        client.close()
        return True
    except OSError:
        return False


# MARK: - Haupt-App -----------------------------------------------------------


class BlitztextApp:
    def __init__(self) -> None:
        self.app_state = AppState()
        self.renderer = TrayIconRenderer()
        self._anim_frame = 0
        self._anim_id: int | None = None

        # AppIndicator (Menüleisten-Symbol)
        self.indicator = AppIndicator.Indicator.new(
            "blitztext", "idle_0", AppIndicator.IndicatorCategory.APPLICATION_STATUS)
        self.indicator.set_icon_theme_path(self.renderer.theme_path)
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.indicator.set_title("Blitztext")
        self.indicator.set_menu(self._build_menu())

        # Popover-Fenster
        self.popover = PopoverWindow(
            self.app_state, on_quit=self.quit, on_install_shortcuts=self.install_shortcuts)

        # Zustand -> Oberfläche verdrahten
        self.app_state.on_menu_bar_status_change = self._on_status_change
        self.app_state.on_ui_refresh = self._on_ui_refresh

        self._render_status(self.app_state.menu_bar_status, 0)

    # MARK: - Menü ------------------------------------------------------------

    def _build_menu(self) -> Gtk.Menu:
        menu = Gtk.Menu()

        open_item = Gtk.MenuItem(label="Blitztext öffnen")
        open_item.connect("activate", lambda _i: self.show_popover())
        menu.append(open_item)
        menu.append(Gtk.SeparatorMenuItem())

        # Schnellstart der vier Workflows
        for t in WorkflowType.main_menu_cases():
            item = Gtk.MenuItem(label=self.app_state.display_name(t))
            item.connect("activate", lambda _i, wf=t: self._start_from_menu(wf))
            menu.append(item)
        menu.append(Gtk.SeparatorMenuItem())

        settings_item = Gtk.MenuItem(label="Einstellungen …")
        settings_item.connect("activate", lambda _i: self._open_settings())
        menu.append(settings_item)

        quit_item = Gtk.MenuItem(label="Beenden")
        quit_item.connect("activate", lambda _i: self.quit())
        menu.append(quit_item)

        menu.show_all()
        return menu

    def _start_from_menu(self, t: WorkflowType) -> None:
        self.app_state.start_workflow(t, LaunchSource.MANUAL)
        self.popover.present_popover()

    def _open_settings(self) -> None:
        from .state import Page
        self.app_state.page = Page.SETTINGS
        self.popover.present_popover()

    def show_popover(self) -> None:
        self.popover.present_popover()

    # MARK: - Status & Animation ----------------------------------------------

    def _on_status_change(self, status: MenuBarStatus) -> None:
        self._anim_frame = 0
        if self._anim_id is not None:
            GLib.source_remove(self._anim_id)
            self._anim_id = None
        if self.renderer.is_animated(status):
            interval = 120 if status.kind is StatusKind.RECORDING else 180
            self._anim_id = GLib.timeout_add(interval, self._animate, status)
        self._render_status(status, 0)

    def _animate(self, status: MenuBarStatus) -> bool:
        self._anim_frame = (self._anim_frame + 1) % 4
        self._render_status(status, self._anim_frame)
        return True

    def _render_status(self, status: MenuBarStatus, frame: int) -> None:
        name = self.renderer.frame_name(status, frame)
        self.indicator.set_icon_full(name, self._tooltip(status))

    @staticmethod
    def _tooltip(status: MenuBarStatus) -> str:
        kind = status.kind
        t = status.workflow_type
        if kind is StatusKind.IDLE:
            return "Blitztext ist bereit"
        name = t.display_name if t else "Blitztext"
        return {
            StatusKind.RECORDING: f"{name}: Aufnahme läuft",
            StatusKind.PROCESSING: f"{name}: Verarbeitung läuft",
            StatusKind.SUCCESS: f"{name}: Fertig",
            StatusKind.ERROR: f"{name}: Fehler",
        }.get(kind, "Blitztext")

    def _on_ui_refresh(self) -> None:
        # Wird teils aus Hintergrund-Threads über GLib.idle_add gerufen -> hier sind wir sicher.
        self.popover.rebuild()

    # MARK: - Tastenkürzel-Befehle (Socket) -----------------------------------

    def start_socket_server(self) -> None:
        path = socket_path()
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(path)
        server.listen(5)

        def loop() -> None:
            while True:
                try:
                    conn, _ = server.accept()
                except OSError:
                    break
                with conn:
                    data = conn.recv(256).decode("utf-8").strip()
                if data:
                    GLib.idle_add(self._handle_trigger, data)

        threading.Thread(target=loop, daemon=True).start()

    def _handle_trigger(self, workflow_name: str) -> bool:
        try:
            t = WorkflowType(workflow_name)
        except ValueError:
            return False

        wf = self.app_state.active_workflow
        # Toggle: läuft schon eine Aufnahme dieses Workflows -> stoppen (= verarbeiten + einfügen).
        if wf and wf.type is t and wf.is_recording:
            self.app_state.stop_current_workflow()
        elif wf and wf.type is t and wf.phase.is_active:
            pass  # verarbeitet gerade -> ignorieren
        else:
            self.app_state.start_workflow(t, LaunchSource.HOTKEY_BACKGROUND)
        return False

    # MARK: - GNOME-Tastenkürzel einrichten -----------------------------------

    def install_shortcuts(self) -> str:
        """Legt Super+1..4 als GNOME-Systemkürzel an (Logik in shortcuts.py)."""
        return shortcuts.install_gnome_shortcuts()

    # MARK: - Lebenszyklus ----------------------------------------------------

    def run(self) -> None:
        self.start_socket_server()
        if self.app_state.should_show_onboarding:
            GLib.idle_add(self.show_popover)
        Gtk.main()

    def quit(self) -> None:
        try:
            os.unlink(socket_path())
        except OSError:
            pass
        Gtk.main_quit()
