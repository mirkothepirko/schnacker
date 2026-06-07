"""Das Popover-Fenster — portiert aus MenuBarView.swift.

Ein schmales, randloses Fenster (wie das macOS-Popover), das je nach Zustand eine
von vier Seiten zeigt: Hauptmenü, Onboarding, Einstellungen, aktiver Workflow.
"""

from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from ..models import Phase, WorkflowType
from ..services import local_transcription as local
from ..state import Page
from .settings_view import SettingsView
from .waveform import WaveformView
from .workflow_row import WorkflowRow

_WIDTH = 360

_CSS = b"""
.popover-root { background-color: @theme_bg_color; }
.app-title { font-weight: 600; font-size: 11pt; }
.app-badge { color: alpha(@theme_fg_color, 0.45); font-size: 9pt; }
.status-ready { font-weight: 700; font-size: 13pt; }
.section-label { font-size: 9pt; font-weight: 600; color: alpha(@theme_fg_color, 0.55); }
.hint-text { font-size: 9pt; color: alpha(@theme_fg_color, 0.6); }
.mono { font-family: monospace; font-size: 9pt; color: alpha(@theme_fg_color, 0.6); }
.workflow-name { font-weight: 500; font-size: 11pt; }
.workflow-subtitle { font-size: 9pt; color: alpha(@theme_fg_color, 0.6); }
.workflow-icon {
    background-color: alpha(@theme_fg_color, 0.06);
    border-radius: 10px;
    font-size: 15pt;
}
.workflow-row:hover { background-color: alpha(@theme_fg_color, 0.05); border-radius: 10px; }
.hotkey-chip {
    background-color: alpha(@theme_fg_color, 0.10);
    border-radius: 6px;
    padding: 2px 7px;
    font-size: 9pt;
    font-weight: 600;
}
.term-chip { background-color: alpha(@theme_fg_color, 0.06); border-radius: 12px; padding: 2px 4px 2px 8px; }
.panel {
    background-color: alpha(@theme_fg_color, 0.035);
    border-radius: 10px;
    padding: 10px;
}
.result-text { font-size: 9pt; color: alpha(@theme_fg_color, 0.6); }
.big-title { font-weight: 600; font-size: 13pt; }
"""


def _install_css(screen) -> None:
    provider = Gtk.CssProvider()
    provider.load_from_data(_CSS)
    Gtk.StyleContext.add_provider_for_screen(
        screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


class PopoverWindow(Gtk.Window):
    def __init__(self, app_state, on_quit: Callable[[], None],
                 on_install_shortcuts: Callable[[], str]) -> None:
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.app_state = app_state
        self.on_quit = on_quit
        self.on_install_shortcuts = on_install_shortcuts

        self.set_decorated(False)
        self.set_resizable(False)
        self.set_skip_taskbar_hint(True)
        self.set_keep_above(True)
        self.set_position(Gtk.WindowPosition.MOUSE)
        self.set_default_size(_WIDTH, -1)
        self.set_size_request(_WIDTH, -1)
        self.get_style_context().add_class("popover-root")

        _install_css(self.get_screen())

        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(self._content)

        self._settings_view: SettingsView | None = None
        self._waveform: WaveformView | None = None
        self._shown_page: Page | None = None

        self.connect("key-press-event", self._on_key_press)
        # Klick neben das Fenster (Fokus verloren) -> schließen, wie ein echtes Popover.
        self.connect("focus-out-event", self._on_focus_out)

    # MARK: - Anzeigen/Verbergen ----------------------------------------------

    def present_popover(self) -> None:
        self.app_state.is_popover_shown = True
        self._prepare_for_presentation()
        self.rebuild()
        self.show_all()
        self.present()

    def hide_popover(self) -> None:
        self.app_state.is_popover_shown = False
        if self._waveform:
            self._waveform.stop()
        self.hide()
        # Nach dem Schließen aufräumen wie popoverDidClose im Original.
        phase = self.app_state.active_workflow.phase.phase if self.app_state.active_workflow else Phase.IDLE
        if phase in (Phase.DONE, Phase.ERROR):
            self.app_state.reset_current_workflow()
        else:
            self.app_state.page = Page.MAIN

    def _prepare_for_presentation(self) -> None:
        st = self.app_state
        if st.active_workflow and st.active_workflow.phase.is_active:
            st.page = Page.WORKFLOW
        elif st.should_show_onboarding:
            st.page = Page.ONBOARDING
            st.mark_onboarding_seen()
        elif st.page in (Page.WORKFLOW, Page.ONBOARDING):
            st.page = Page.MAIN

    def _on_key_press(self, _w, event) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            wf = self.app_state.active_workflow
            if wf and wf.phase.is_active:
                self.app_state.stop_current_workflow()
            else:
                self.hide_popover()
            return True
        return False

    def _on_focus_out(self, _w, _e) -> bool:
        # Nicht schließen, während aufgenommen/verarbeitet wird (sonst bricht es ab).
        wf = self.app_state.active_workflow
        if wf and wf.phase.is_active and wf.phase.phase is Phase.RUNNING:
            return False
        self.hide_popover()
        return False

    # MARK: - Aufbau ----------------------------------------------------------

    def rebuild(self) -> None:
        """Baut die aktuelle Seite neu auf. Die Einstellungsseite bleibt bestehen
        (damit beim Tippen nicht der Fokus verloren geht)."""
        if not self.app_state.is_popover_shown:
            return
        page = self.app_state.page
        if page is Page.SETTINGS and self._shown_page is Page.SETTINGS:
            return  # Einstellungen aktualisieren sich selbst.

        # Alten Wellenform-Timer stoppen, sonst läuft er auf einem zerstörten Widget weiter.
        if self._waveform is not None:
            self._waveform.stop()
            self._waveform = None

        # Die persistente Einstellungsseite herauslösen, damit sie beim Zerstören
        # der alten Seite erhalten bleibt (sonst Fehler "widget already has parent").
        if self._settings_view is not None and self._settings_view.get_parent() is not None:
            self._settings_view.get_parent().remove(self._settings_view)

        for child in self._content.get_children():
            child.destroy()

        if page is Page.MAIN:
            self._content.add(self._build_main())
        elif page is Page.ONBOARDING:
            self._content.add(self._build_onboarding())
        elif page is Page.SETTINGS:
            self._content.add(self._build_settings())
        elif page is Page.WORKFLOW:
            self._content.add(self._build_workflow())

        self._shown_page = page
        self._content.show_all()

    # MARK: - Hauptseite ------------------------------------------------------

    def _build_main(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Kopfzeile
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.set_margin_top(12)
        header.set_margin_start(16)
        header.set_margin_end(16)
        header.set_margin_bottom(8)
        title = Gtk.Label(label="Schnacker")
        title.get_style_context().add_class("app-title")
        header.pack_start(title, False, False, 0)
        badge = Gtk.Label(label="Ubuntu Preview")
        badge.get_style_context().add_class("app-badge")
        header.pack_start(badge, False, False, 0)
        gear = Gtk.Button()
        gear.set_relief(Gtk.ReliefStyle.NONE)
        gear.add(Gtk.Image.new_from_icon_name("emblem-system-symbolic", Gtk.IconSize.BUTTON))
        gear.connect("clicked", lambda _b: self._go(Page.SETTINGS))
        header.pack_end(gear, False, False, 0)
        box.pack_start(header, False, False, 0)

        # Status
        if self.app_state.is_configured:
            status = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            status.set_halign(Gtk.Align.CENTER)
            dot = Gtk.Label(label="●")
            dot.get_style_context().add_class("status-ready")
            ready = Gtk.Label(label="Bereit")
            ready.get_style_context().add_class("status-ready")
            status.pack_start(dot, False, False, 0)
            status.pack_start(ready, False, False, 0)
            box.pack_start(status, False, False, 0)
        else:
            box.pack_start(self._unconfigured_header(), False, False, 0)

        box.pack_start(self._mode_panel(), False, False, 0)

        # Workflow-Liste
        list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        list_box.set_margin_top(8)
        for t in WorkflowType.main_menu_cases():
            row = WorkflowRow(
                t, enabled=self.app_state.is_workflow_available(t),
                name=self.app_state.display_name(t),
                subtitle=self.app_state.workflow_subtitle(t),
                on_click=self._start_workflow)
            list_box.pack_start(row, False, False, 0)
        box.pack_start(list_box, False, False, 0)

        box.pack_start(self._footer(), False, False, 0)
        return box

    def _unconfigured_header(self) -> Gtk.Box:
        b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        b.set_halign(Gtk.Align.CENTER)
        b.set_margin_top(6)
        title = Gtk.Label(label="Einrichtung nötig")
        title.get_style_context().add_class("big-title")
        b.pack_start(title, False, False, 0)
        sub = Gtk.Label(label="Öffne die Einstellungen und hinterlege deinen OpenAI API Key,\n"
                              "oder lade ein lokales Modell, um loszulegen.")
        sub.get_style_context().add_class("hint-text")
        sub.set_justify(Gtk.Justification.CENTER)
        b.pack_start(sub, False, False, 0)
        btn = Gtk.Button(label="Einstellungen öffnen")
        btn.connect("clicked", lambda _b: self._go(Page.SETTINGS))
        b.pack_start(btn, False, False, 0)
        return b

    def _mode_panel(self) -> Gtk.Box:
        st = self.app_state
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        panel.get_style_context().add_class("panel")
        panel.set_margin_start(16)
        panel.set_margin_end(16)
        panel.set_margin_top(12)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        secure = st.settings.app.secure_local_mode_enabled
        icon = Gtk.Label(label="🔒" if secure else "🌐")
        top.pack_start(icon, False, False, 0)
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name = Gtk.Label(label="Sicherer lokaler Modus" if secure else "Online Whisper", xalign=0)
        name.get_style_context().add_class("workflow-name")
        sub_text = (f"Lokal mit {st.selected_local_model_display}." if secure and st.selected_local_model_is_installed
                    else "Schnacker nutzt gerade die OpenAI-Transkription." if not secure
                    else f"{st.selected_local_model_display} ist noch nicht installiert.")
        sub = Gtk.Label(label=sub_text, xalign=0)
        sub.get_style_context().add_class("workflow-subtitle")
        sub.set_line_wrap(True)
        text_box.pack_start(name, False, False, 0)
        text_box.pack_start(sub, False, False, 0)
        top.pack_start(text_box, True, True, 0)

        switch = Gtk.Switch()
        switch.set_valign(Gtk.Align.CENTER)
        switch.set_active(secure)
        switch.connect("notify::active", self._on_mode_switch)
        top.pack_end(switch, False, False, 0)
        panel.pack_start(top, False, False, 0)
        return panel

    def _on_mode_switch(self, switch, _param) -> None:
        if switch.get_active():
            self.app_state.enable_secure_local_mode()
        else:
            self.app_state.settings.app.secure_local_mode_enabled = False
            self.app_state.save_settings()
        self.app_state.page = Page.MAIN
        self._shown_page = None
        self.rebuild()

    # MARK: - Onboarding ------------------------------------------------------

    def _build_onboarding(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_top(14)
        box.set_margin_bottom(14)
        box.set_margin_start(16)
        box.set_margin_end(16)

        title = Gtk.Label(label="Willkommen bei Schnacker", xalign=0)
        title.get_style_context().add_class("big-title")
        box.pack_start(title, False, False, 0)

        intro = Gtk.Label(
            label="Einmal einrichten, dann direkt loslegen: OpenAI API Key eintragen "
                  "(oder lokales Modell laden), danach sprechen und einfügen.", xalign=0)
        intro.get_style_context().add_class("hint-text")
        intro.set_line_wrap(True)
        box.pack_start(intro, False, False, 0)

        steps = [
            ("1", "OpenAI Key speichern", "Öffne die Einstellungen und trage deinen OpenAI API Key ein."),
            ("2", "Auto-Einfügen einrichten", "Einmal ./setup.sh ausführen (installiert ydotool)."),
            ("3", "Workflow wählen", "Schnacker oder einen Verbesserer-Workflow aus dem Menü starten."),
        ]
        for number, head, detail in steps:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            num = Gtk.Label(label=number)
            num.get_style_context().add_class("workflow-name")
            row.pack_start(num, False, False, 0)
            tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            h = Gtk.Label(label=head, xalign=0)
            h.get_style_context().add_class("workflow-name")
            d = Gtk.Label(label=detail, xalign=0)
            d.get_style_context().add_class("hint-text")
            d.set_line_wrap(True)
            tb.pack_start(h, False, False, 0)
            tb.pack_start(d, False, False, 0)
            row.pack_start(tb, True, True, 0)
            box.pack_start(row, False, False, 0)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        setup_btn = Gtk.Button(label="Jetzt einrichten")
        setup_btn.connect("clicked", lambda _b: self._go(Page.SETTINGS))
        buttons.pack_start(setup_btn, False, False, 0)
        later_btn = Gtk.Button(label="Später")
        later_btn.set_relief(Gtk.ReliefStyle.NONE)
        later_btn.connect("clicked", lambda _b: self._go(Page.MAIN))
        buttons.pack_start(later_btn, False, False, 0)
        box.pack_start(buttons, False, False, 0)
        return box

    # MARK: - Einstellungen ---------------------------------------------------

    def _build_settings(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_size_request(_WIDTH, 460)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.set_margin_top(10)
        header.set_margin_bottom(10)
        header.set_margin_start(16)
        header.set_margin_end(16)
        back = Gtk.Button(label="‹ Zurück")
        back.set_relief(Gtk.ReliefStyle.NONE)
        back.connect("clicked", lambda _b: self._go(Page.MAIN))
        header.pack_start(back, False, False, 0)
        title = Gtk.Label(label="Einstellungen")
        title.get_style_context().add_class("app-title")
        header.set_center_widget(title)
        box.pack_start(header, False, False, 0)
        box.pack_start(Gtk.Separator(), False, False, 0)

        if self._settings_view is None:
            self._settings_view = SettingsView(self.app_state, self.on_install_shortcuts)
        box.pack_start(self._settings_view, True, True, 0)
        return box

    # MARK: - Aktiver Workflow ------------------------------------------------

    def _build_workflow(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        wf = self.app_state.active_workflow
        if wf is None:
            return self._build_main()

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.set_margin_top(10)
        header.set_margin_bottom(10)
        header.set_margin_start(16)
        header.set_margin_end(16)
        back = Gtk.Button(label="‹ Zurück")
        back.set_relief(Gtk.ReliefStyle.NONE)
        back.connect("clicked", lambda _b: self.app_state.reset_current_workflow())
        header.pack_start(back, False, False, 0)
        title = Gtk.Label(label=self.app_state.display_name(wf.type))
        title.get_style_context().add_class("app-title")
        header.set_center_widget(title)
        box.pack_start(header, False, False, 0)
        box.pack_start(Gtk.Separator(), False, False, 0)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(20)
        content.set_margin_bottom(20)
        content.set_margin_start(16)
        content.set_margin_end(16)

        ph = wf.phase
        if ph.phase in (Phase.IDLE, Phase.RUNNING) and wf.is_recording:
            content.pack_start(self._recording_view(wf), False, False, 0)
        elif ph.phase in (Phase.IDLE, Phase.RUNNING):
            content.pack_start(self._processing_view(ph.text or "Wird verarbeitet …"), False, False, 0)
        elif ph.phase is Phase.DONE:
            content.pack_start(self._done_view(ph.text), False, False, 0)
        elif ph.phase is Phase.ERROR:
            content.pack_start(self._error_view(ph.text, wf), False, False, 0)

        box.pack_start(content, True, True, 0)
        box.pack_start(self._footer(), False, False, 0)
        return box

    def _recording_view(self, wf) -> Gtk.Box:
        b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self._waveform = WaveformView(level_provider=lambda: wf.audio_level)
        self._waveform.start()
        b.pack_start(self._waveform, False, False, 0)

        stop = Gtk.Button(label="⏹")
        stop.set_halign(Gtk.Align.CENTER)
        stop.connect("clicked", lambda _b: self.app_state.stop_current_workflow())
        b.pack_start(stop, False, False, 0)

        hint = Gtk.Label(label="Ich höre zu … Klicke zum Stoppen.")
        hint.get_style_context().add_class("hint-text")
        b.pack_start(hint, False, False, 0)
        return b

    def _processing_view(self, message: str) -> Gtk.Box:
        b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        spinner = Gtk.Spinner()
        spinner.start()
        b.pack_start(spinner, False, False, 0)
        lbl = Gtk.Label(label=message)
        lbl.get_style_context().add_class("hint-text")
        lbl.set_line_wrap(True)
        b.pack_start(lbl, False, False, 0)
        return b

    def _done_view(self, text: str) -> Gtk.Box:
        b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        check = Gtk.Label(label="✅")
        b.pack_start(check, False, False, 0)
        # Beschriftung je nach Quelle: automatisch eingefügt oder nur kopiert.
        from ..models import LaunchSource
        was_pasted = self.app_state._active_launch_source is LaunchSource.HOTKEY_BACKGROUND
        head = Gtk.Label(label="Eingefügt" if was_pasted else "In Zwischenablage kopiert")
        head.get_style_context().add_class("big-title")
        b.pack_start(head, False, False, 0)
        if not was_pasted:
            hint = Gtk.Label(label="Mit Strg+V einfügen.")
            hint.get_style_context().add_class("hint-text")
            b.pack_start(hint, False, False, 0)
        result = Gtk.Label(label=text)
        result.get_style_context().add_class("result-text")
        result.set_line_wrap(True)
        result.set_max_width_chars(40)
        result.set_lines(3)
        result.set_ellipsize(3)  # Pango.EllipsizeMode.END
        result.set_justify(Gtk.Justification.CENTER)
        b.pack_start(result, False, False, 0)
        return b

    def _error_view(self, message: str, wf) -> Gtk.Box:
        b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        icon = Gtk.Label(label="⚠️")
        b.pack_start(icon, False, False, 0)
        lbl = Gtk.Label(label=message)
        lbl.get_style_context().add_class("hint-text")
        lbl.set_line_wrap(True)
        lbl.set_justify(Gtk.Justification.CENTER)
        b.pack_start(lbl, False, False, 0)
        retry = Gtk.Button(label="Nochmal versuchen")
        retry.connect("clicked", lambda _b: self._retry(wf))
        b.pack_start(retry, False, False, 0)
        return b

    def _retry(self, wf) -> None:
        wf.reset()
        wf.start()
        self.app_state.page = Page.WORKFLOW
        self.rebuild()

    # MARK: - Gemeinsames -----------------------------------------------------

    def _footer(self) -> Gtk.Box:
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        footer.set_margin_top(8)
        footer.set_margin_bottom(8)
        quit_btn = Gtk.Button(label="Beenden")
        quit_btn.set_relief(Gtk.ReliefStyle.NONE)
        quit_btn.get_style_context().add_class("hint-text")
        quit_btn.set_halign(Gtk.Align.CENTER)
        quit_btn.connect("clicked", lambda _b: self.on_quit())
        footer.set_center_widget(quit_btn)
        return footer

    def _go(self, page: Page) -> None:
        self.app_state.page = page
        self.rebuild()

    def _start_workflow(self, t: WorkflowType) -> None:
        self.app_state.start_workflow(t)
        self.rebuild()
