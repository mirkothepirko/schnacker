"""Wellenform-Anzeige während der Aufnahme — portiert aus WaveformView.swift.

40 schmale Balken, deren Höhe vom aktuellen Mikrofon-Pegel abhängt. Ein Timer
(30x pro Sekunde) schiebt die Balken nach links weiter und hängt rechts einen
neuen Wert an — so entsteht der "scrollende" Wellen-Effekt.
"""

from __future__ import annotations

import math
import random
from typing import Callable

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

_BAR_COUNT = 40
_MIN_LEVEL = 0.03
# Akzentfarbe #F2A600 (Gold) aus der gemeinsamen Palette, als Cairo-RGB (0..1).
_BAR_RGB = (0.949, 0.651, 0.0)


class WaveformView(Gtk.DrawingArea):
    def __init__(self, level_provider: Callable[[], float]) -> None:
        super().__init__()
        self._level_provider = level_provider  # liefert den aktuellen Pegel (0..1)
        self._levels = [_MIN_LEVEL] * _BAR_COUNT
        self._phase = 0.0
        self._timer_id: int | None = None
        self.set_size_request(-1, 44)
        self.connect("draw", self._on_draw)

    def start(self) -> None:
        if self._timer_id is None:
            self._timer_id = GLib.timeout_add(int(1000 / 30), self._tick)

    def stop(self) -> None:
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        self._levels = [_MIN_LEVEL] * _BAR_COUNT
        self.queue_draw()

    def _tick(self) -> bool:
        # Exakt wie im Original: Grundpegel + leichtes Zittern + "Atmen".
        self._phase += 0.15
        base = float(self._level_provider())
        jitter = random.uniform(-0.06, 0.06)
        breathe = math.sin(self._phase) * 0.03
        new_level = max(_MIN_LEVEL, min(1.0, base + jitter + breathe))
        self._levels.pop(0)
        self._levels.append(new_level)
        self.queue_draw()
        return True  # Timer wiederholt sich

    def _on_draw(self, _widget, ctx) -> bool:
        allocation = self.get_allocation()
        width, height = allocation.width, allocation.height
        bar_width = 2.5
        spacing = (width - _BAR_COUNT * bar_width) / max(1, _BAR_COUNT - 1)

        for i, level in enumerate(self._levels):
            bar_h = max(2.0, level * height)
            x = i * (bar_width + spacing)
            y = (height - bar_h) / 2
            opacity = 0.25 + level * 0.75
            ctx.set_source_rgba(*_BAR_RGB, opacity)
            self._rounded_bar(ctx, x, y, bar_width, bar_h)
            ctx.fill()
        return False

    @staticmethod
    def _rounded_bar(ctx, x: float, y: float, w: float, h: float) -> None:
        r = w / 2
        ctx.new_sub_path()
        ctx.arc(x + r, y + r, r, math.pi, 2 * math.pi)
        ctx.arc(x + r, y + h - r, r, 0, math.pi)
        ctx.close_path()
