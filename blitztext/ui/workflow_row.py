"""Eine Zeile in der Workflow-Liste — portiert aus WorkflowRowView.swift.

Zeigt Symbol, Name, Untertitel und ein Tastenkürzel-Abzeichen. Klick startet
den Workflow. Deaktivierte Workflows (z.B. ohne API-Key) werden ausgegraut.
"""

from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from ..models import WorkflowType
from .. import shortcuts

# Emoji als Symbol — überall verfügbar, ausdrucksstark, keine fehlenden Icons.
_WORKFLOW_EMOJI: dict[WorkflowType, str] = {
    WorkflowType.TRANSCRIPTION: "🎙️",
    WorkflowType.TEXT_IMPROVER: "✨",
    WorkflowType.DAMPF_ABLASSEN: "🌾",
    WorkflowType.EMOJI_TEXT: "🇨🇭",
}


class WorkflowRow(Gtk.Button):
    def __init__(self, t: WorkflowType, enabled: bool, name: str, subtitle: str,
                 on_click: Callable[[WorkflowType], None]) -> None:
        super().__init__()
        self.set_relief(Gtk.ReliefStyle.NONE)
        self.set_sensitive(enabled)
        self.get_style_context().add_class("workflow-row")
        self.connect("clicked", lambda _b: on_click(t))

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.set_margin_top(6)
        row.set_margin_bottom(6)
        row.set_margin_start(10)
        row.set_margin_end(10)

        # Symbol in einem abgerundeten Kästchen
        icon = Gtk.Label(label=_WORKFLOW_EMOJI.get(t, "•"))
        icon.set_size_request(36, 36)
        icon.get_style_context().add_class("workflow-icon")
        row.pack_start(icon, False, False, 0)

        # Name + Untertitel (untereinander)
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_valign(Gtk.Align.CENTER)
        name_label = Gtk.Label(label=name, xalign=0)
        name_label.get_style_context().add_class("workflow-name")
        sub_label = Gtk.Label(label=subtitle, xalign=0)
        sub_label.get_style_context().add_class("workflow-subtitle")
        text_box.pack_start(name_label, False, False, 0)
        text_box.pack_start(sub_label, False, False, 0)
        row.pack_start(text_box, True, True, 0)

        # Tastenkürzel-Abzeichen rechts
        badge = self._make_hotkey_badge(shortcuts.label_for(t))
        badge.set_valign(Gtk.Align.CENTER)
        row.pack_end(badge, False, False, 0)

        self.add(row)

    @staticmethod
    def _make_hotkey_badge(label: str) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        if not label:
            return box
        for key in label.split("+"):
            chip = Gtk.Label(label=key.strip())
            chip.get_style_context().add_class("hotkey-chip")
            box.pack_start(chip, False, False, 0)
        return box
