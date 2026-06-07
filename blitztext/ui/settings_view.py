"""Einstellungen — portiert aus SettingsContentView.swift.

Zwei Tabs:
    "Anpassen"  -> lokaler Modus, Tastenkürzel, die drei KI-Workflows, Eigennamen
    "Zugang"    -> OpenAI API-Key, Auto-Einfügen-Status, GNOME-Kürzel einrichten

Die Einstellungen werden direkt beim Ändern gespeichert (app_state.save_settings()).
"""

from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from .. import shortcuts
from ..models import HotkeyMode, TextTone, WorkflowType
from ..services import keychain
from ..services import local_transcription as local
from ..services import paste


def _section_label(text: str) -> Gtk.Label:
    label = Gtk.Label(label=text.upper(), xalign=0)
    label.get_style_context().add_class("section-label")
    return label


class SettingsView(Gtk.Box):
    def __init__(self, app_state, on_install_shortcuts: Callable[[], str]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.app_state = app_state
        self.on_install_shortcuts = on_install_shortcuts

        notebook = Gtk.Notebook()
        notebook.set_show_border(False)
        notebook.append_page(self._scroll(self._build_customize()), Gtk.Label(label="Anpassen"))
        notebook.append_page(self._scroll(self._build_access()), Gtk.Label(label="Zugang"))
        self.pack_start(notebook, True, True, 0)

        # Standard-Tab wie im Original: ohne API-Key zuerst "Zugang" zeigen.
        notebook.set_current_page(0 if keychain.is_configured() else 1)

        # Modell-Download-Status regelmäßig auffrischen, solange die Seite offen ist.
        self._poll_id = GLib.timeout_add(500, self._poll_dynamic)
        self.connect("destroy", lambda _w: self._stop_poll())

    @staticmethod
    def _scroll(child: Gtk.Widget) -> Gtk.ScrolledWindow:
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.add(child)
        return scroller

    def _stop_poll(self) -> None:
        if self._poll_id is not None:
            GLib.source_remove(self._poll_id)
            self._poll_id = None

    # MARK: - Tab "Anpassen" --------------------------------------------------

    def _build_customize(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)

        box.pack_start(self._local_mode_section(), False, False, 0)
        box.pack_start(self._hotkey_section(), False, False, 0)
        box.pack_start(self._text_improver_section(), False, False, 0)
        box.pack_start(self._dampf_section(), False, False, 0)
        box.pack_start(self._emoji_section(), False, False, 0)
        box.pack_start(self._terms_section(), False, False, 0)
        return box

    def _local_mode_section(self) -> Gtk.Box:
        s = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        s.pack_start(_section_label("Sicherer Lokaler Modus"), False, False, 0)

        toggle_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toggle_row.pack_start(Gtk.Label(label="Sicherer Lokaler Modus", xalign=0), True, True, 0)
        self._local_switch = Gtk.Switch()
        self._local_switch.set_active(self.app_state.settings.app.secure_local_mode_enabled)
        self._local_switch.connect("notify::active", self._on_local_mode_toggled)
        toggle_row.pack_end(self._local_switch, False, False, 0)
        s.pack_start(toggle_row, False, False, 0)

        # Modell-Auswahl
        model_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        model_row.pack_start(Gtk.Label(label="Lokales Modell", xalign=0), False, False, 0)
        self._model_combo = Gtk.ComboBoxText()
        for name in local.model_options():
            installed = " · Installiert" if local.is_model_installed(name) else " · Nicht installiert"
            self._model_combo.append(name, local.display_name(name) + installed)
        self._model_combo.set_active_id(self.app_state.selected_local_model_name)
        self._model_combo.connect("changed", self._on_model_changed)
        model_row.pack_start(self._model_combo, True, True, 0)
        s.pack_start(model_row, False, False, 0)

        self._install_button = Gtk.Button(label=self._install_button_label())
        self._install_button.connect("clicked", lambda _b: self.app_state.install_selected_local_model())
        s.pack_start(self._install_button, False, False, 0)

        self._model_status = Gtk.Label(xalign=0)
        self._model_status.get_style_context().add_class("hint-text")
        self._model_status.set_line_wrap(True)
        s.pack_start(self._model_status, False, False, 0)
        return s

    def _install_button_label(self) -> str:
        name = self.app_state.selected_local_model_name
        if local.is_model_installed(name):
            return f"{local.display_name(name)} ist installiert"
        return f"{local.display_name(name)} installieren"

    def _on_local_mode_toggled(self, switch, _param) -> None:
        active = switch.get_active()
        if active and not self.app_state.selected_local_model_is_installed:
            self.app_state.enable_secure_local_mode()
        else:
            self.app_state.settings.app.secure_local_mode_enabled = active
            self.app_state.save_settings()

    def _on_model_changed(self, combo) -> None:
        model_id = combo.get_active_id()
        if model_id:
            self.app_state.settings.app.selected_local_transcription_model_name = model_id
            self.app_state.save_settings()
            self._install_button.set_label(self._install_button_label())

    def _hotkey_section(self) -> Gtk.Box:
        s = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        s.pack_start(_section_label("Tastenkürzel"), False, False, 0)

        for t in WorkflowType.main_menu_cases():
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            kbd = Gtk.Label(label=shortcuts.label_for(t), xalign=0)
            kbd.get_style_context().add_class("mono")
            kbd.set_size_request(110, -1)
            row.pack_start(kbd, False, False, 0)
            row.pack_start(Gtk.Label(label=self.app_state.display_name(t), xalign=0), True, True, 0)
            s.pack_start(row, False, False, 0)

        # Modus (Halten/Drücken). Hinweis: unter Wayland verhält sich "Halten" wie "Drücken".
        mode_label = Gtk.Label(label="Modus", xalign=0)
        mode_label.get_style_context().add_class("hint-text")
        s.pack_start(mode_label, False, False, 0)

        self._mode_combo = Gtk.ComboBoxText()
        for mode in HotkeyMode:
            self._mode_combo.append(mode.value, mode.display_name)
        self._mode_combo.set_active_id(self.app_state.settings.app.hotkey_mode.value)
        self._mode_combo.connect("changed", self._on_mode_changed)
        s.pack_start(self._mode_combo, False, False, 0)

        note = Gtk.Label(
            label="Hinweis: Unter Wayland startet/stoppt das Kürzel die Aufnahme (Drücken-Modus).",
            xalign=0)
        note.get_style_context().add_class("hint-text")
        note.set_line_wrap(True)
        s.pack_start(note, False, False, 0)
        return s

    def _on_mode_changed(self, combo) -> None:
        mode_id = combo.get_active_id()
        if mode_id:
            self.app_state.settings.app.hotkey_mode = HotkeyMode(mode_id)
            self.app_state.save_settings()

    def _text_improver_section(self) -> Gtk.Box:
        s = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        s.pack_start(_section_label("Blitztext+"), False, False, 0)

        s.pack_start(Gtk.Label(label="Schreibstil", xalign=0), False, False, 0)
        self._tone_combo = Gtk.ComboBoxText()
        for tone in TextTone:
            self._tone_combo.append(tone.value, tone.display_name)
        self._tone_combo.set_active_id(self.app_state.settings.text_improvement.tone.value)
        self._tone_combo.connect("changed", lambda c: self._set_tone(c.get_active_id()))
        s.pack_start(self._tone_combo, False, False, 0)

        s.pack_start(Gtk.Label(label="Eigene Anweisung", xalign=0), False, False, 0)
        self._improver_prompt = self._make_textview(
            self.app_state.settings.text_improvement.system_prompt, height=64)
        self._improver_prompt.get_buffer().connect("changed", self._on_improver_prompt_changed)
        s.pack_start(self._frame(self._improver_prompt), False, False, 0)

        s.pack_start(Gtk.Label(label="Kontext", xalign=0), False, False, 0)
        self._context_entry = Gtk.Entry()
        self._context_entry.set_placeholder_text('z.B. "E-Mails im Bereich Unternehmensberatung"')
        self._context_entry.set_text(self.app_state.settings.text_improvement.context)
        self._context_entry.connect("changed", self._on_context_changed)
        s.pack_start(self._context_entry, False, False, 0)
        return s

    def _set_tone(self, tone_id) -> None:
        if tone_id:
            self.app_state.settings.text_improvement.tone = TextTone(tone_id)
            self.app_state.save_settings()

    def _on_improver_prompt_changed(self, buf) -> None:
        self.app_state.settings.text_improvement.system_prompt = self._buffer_text(buf)
        self.app_state.save_settings()

    def _on_context_changed(self, entry) -> None:
        self.app_state.settings.text_improvement.context = entry.get_text()
        self.app_state.save_settings()

    def _dampf_section(self) -> Gtk.Box:
        s = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        s.pack_start(_section_label("Blitztext Platt"), False, False, 0)
        s.pack_start(Gtk.Label(label="Eigene Anweisung", xalign=0), False, False, 0)
        self._dampf_prompt = self._make_textview(
            self.app_state.settings.dampf_ablassen.system_prompt, height=90)
        self._dampf_prompt.get_buffer().connect("changed", self._on_dampf_prompt_changed)
        s.pack_start(self._frame(self._dampf_prompt), False, False, 0)
        return s

    def _on_dampf_prompt_changed(self, buf) -> None:
        self.app_state.settings.dampf_ablassen.system_prompt = self._buffer_text(buf)
        self.app_state.save_settings()

    def _emoji_section(self) -> Gtk.Box:
        s = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        s.pack_start(_section_label("Blitztext Basel"), False, False, 0)
        s.pack_start(Gtk.Label(label="Eigene Anweisung", xalign=0), False, False, 0)
        self._emoji_prompt = self._make_textview(
            self.app_state.settings.emoji_text.system_prompt, height=90)
        self._emoji_prompt.get_buffer().connect("changed", self._on_emoji_prompt_changed)
        s.pack_start(self._frame(self._emoji_prompt), False, False, 0)
        return s

    def _on_emoji_prompt_changed(self, buf) -> None:
        self.app_state.settings.emoji_text.system_prompt = self._buffer_text(buf)
        self.app_state.save_settings()

    def _terms_section(self) -> Gtk.Box:
        s = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        s.pack_start(_section_label("Eigennamen"), False, False, 0)

        self._terms_flow = Gtk.FlowBox()
        self._terms_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._terms_flow.set_max_children_per_line(4)
        s.pack_start(self._terms_flow, False, False, 0)
        self._rebuild_terms()

        add_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._term_entry = Gtk.Entry()
        self._term_entry.set_placeholder_text("Neuer Begriff")
        self._term_entry.connect("activate", lambda _e: self._add_term())
        add_row.pack_start(self._term_entry, True, True, 0)
        add_btn = Gtk.Button(label="+")
        add_btn.connect("clicked", lambda _b: self._add_term())
        add_row.pack_start(add_btn, False, False, 0)
        s.pack_start(add_row, False, False, 0)
        return s

    def _rebuild_terms(self) -> None:
        for child in self._terms_flow.get_children():
            self._terms_flow.remove(child)
        for term in self.app_state.settings.text_improvement.custom_terms:
            chip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            chip.get_style_context().add_class("term-chip")
            chip.pack_start(Gtk.Label(label=term), False, False, 0)
            remove = Gtk.Button(label="×")
            remove.set_relief(Gtk.ReliefStyle.NONE)
            remove.connect("clicked", lambda _b, t=term: self._remove_term(t))
            chip.pack_start(remove, False, False, 0)
            self._terms_flow.add(chip)
        self._terms_flow.show_all()

    def _add_term(self) -> None:
        term = self._term_entry.get_text().strip()
        terms = self.app_state.settings.text_improvement.custom_terms
        if term and term not in terms:
            terms.append(term)
            self.app_state.save_settings()
            self._term_entry.set_text("")
            self._rebuild_terms()

    def _remove_term(self, term: str) -> None:
        terms = self.app_state.settings.text_improvement.custom_terms
        if term in terms:
            terms.remove(term)
            self.app_state.save_settings()
            self._rebuild_terms()

    # MARK: - Tab "Zugang" ----------------------------------------------------

    def _build_access(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)

        # OpenAI API-Key
        key_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        key_section.pack_start(_section_label("OpenAI API Key"), False, False, 0)

        self._api_entry = Gtk.Entry()
        self._api_entry.set_visibility(False)  # als Passwort behandeln
        self._api_entry.set_placeholder_text("sk-...")
        if keychain.is_configured():
            self._api_entry.set_placeholder_text("Gespeichert — zum Ändern neuen Key eintragen")
        key_section.pack_start(self._api_entry, False, False, 0)

        key_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        paste_btn = Gtk.Button(label="Aus Zwischenablage einfügen")
        paste_btn.connect("clicked", self._on_paste_key)
        key_buttons.pack_start(paste_btn, False, False, 0)
        save_btn = Gtk.Button(label="Speichern")
        save_btn.get_style_context().add_class("suggested-action")
        save_btn.connect("clicked", self._on_save_key)
        key_buttons.pack_start(save_btn, False, False, 0)
        key_section.pack_start(key_buttons, False, False, 0)

        self._key_status = Gtk.Label(xalign=0)
        self._key_status.get_style_context().add_class("hint-text")
        self._key_status.set_line_wrap(True)
        key_section.pack_start(self._key_status, False, False, 0)

        hint = Gtk.Label(
            label="Dein Key bleibt lokal im GNOME-Schlüsselbund. Audio und Text werden direkt "
                  "an die OpenAI API gesendet.", xalign=0)
        hint.get_style_context().add_class("hint-text")
        hint.set_line_wrap(True)
        key_section.pack_start(hint, False, False, 0)
        box.pack_start(key_section, False, False, 0)

        # Auto-Einfügen-Status
        paste_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        paste_section.pack_start(_section_label("Auto-Einfügen"), False, False, 0)
        available = paste.is_auto_paste_available()
        status = ("Auto-Einfügen ist bereit (ydotool installiert)." if available
                  else "ydotool fehlt — Text wird nur in die Zwischenablage gelegt. "
                       "Führe ./setup.sh aus, um Auto-Einfügen zu aktivieren.")
        lbl = Gtk.Label(label=status, xalign=0)
        lbl.get_style_context().add_class("hint-text")
        lbl.set_line_wrap(True)
        paste_section.pack_start(lbl, False, False, 0)
        box.pack_start(paste_section, False, False, 0)

        # GNOME-Tastenkürzel einrichten
        shortcut_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        shortcut_section.pack_start(_section_label("Tastenkürzel einrichten"), False, False, 0)
        sc_hint = Gtk.Label(
            label="Legt die Systemkürzel Super+1 bis Super+4 für die vier Workflows an.", xalign=0)
        sc_hint.get_style_context().add_class("hint-text")
        sc_hint.set_line_wrap(True)
        shortcut_section.pack_start(sc_hint, False, False, 0)
        sc_btn = Gtk.Button(label="GNOME-Kürzel einrichten")
        sc_btn.connect("clicked", self._on_install_shortcuts)
        shortcut_section.pack_start(sc_btn, False, False, 0)
        self._shortcut_status = Gtk.Label(xalign=0)
        self._shortcut_status.get_style_context().add_class("hint-text")
        self._shortcut_status.set_line_wrap(True)
        shortcut_section.pack_start(self._shortcut_status, False, False, 0)
        box.pack_start(shortcut_section, False, False, 0)
        return box

    def _on_save_key(self, _btn) -> None:
        key = self._api_entry.get_text().strip()
        if not key:
            self._key_status.set_text("Bitte trage deinen OpenAI API Key ein.")
            return
        try:
            keychain.invalidate_cache()
            keychain.save(keychain.KeychainKey.OPEN_AI_API_KEY, key)
            self._api_entry.set_text("")
            self._api_entry.set_placeholder_text("Gespeichert — zum Ändern neuen Key eintragen")
            self._key_status.set_text("Gespeichert ✓")
            self.app_state._refresh_ui()
        except Exception as exc:  # noqa: BLE001
            self._key_status.set_text(f"Konnte nicht gespeichert werden: {exc}")

    def _on_paste_key(self, _btn) -> None:
        clipboard = Gtk.Clipboard.get_default(self.get_display())
        text = clipboard.wait_for_text() or ""
        first_line = text.splitlines()[0].strip() if text.strip() else ""
        if first_line.startswith("sk-") and len(first_line) > 20:
            self._api_entry.set_text(first_line)
            self._key_status.set_text("Key eingefügt — jetzt auf Speichern klicken.")
        else:
            self._key_status.set_text("Zwischenablage enthält keinen plausiblen OpenAI API Key.")

    def _on_install_shortcuts(self, _btn) -> None:
        result = self.on_install_shortcuts()
        self._shortcut_status.set_text(result)

    # MARK: - Dynamische Auffrischung -----------------------------------------

    def _poll_dynamic(self) -> bool:
        st = self.app_state
        if st.local_model_error_text:
            self._model_status.set_text(st.local_model_error_text)
        elif st.local_model_status_text:
            self._model_status.set_text(st.local_model_status_text)
        else:
            self._model_status.set_text("")
        self._install_button.set_sensitive(not st.local_model_downloading)
        return True

    # MARK: - Hilfsfunktionen --------------------------------------------------

    @staticmethod
    def _make_textview(text: str, height: int) -> Gtk.TextView:
        view = Gtk.TextView()
        view.set_wrap_mode(Gtk.WrapMode.WORD)
        view.get_buffer().set_text(text)
        view.set_size_request(-1, height)
        return view

    @staticmethod
    def _buffer_text(buf: Gtk.TextBuffer) -> str:
        start, end = buf.get_bounds()
        return buf.get_text(start, end, True)

    @staticmethod
    def _frame(child: Gtk.Widget) -> Gtk.Frame:
        frame = Gtk.Frame()
        frame.add(child)
        return frame
