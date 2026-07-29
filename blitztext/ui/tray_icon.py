"""Menüleisten-Symbol mit Status-Animation — portiert aus MenuBarStatusController.swift.

Das Original zeichnet ein Logo aus vier Streifen (oben breit, unten schmal) und legt
je nach Status ein kleines, pulsierendes Abzeichen darüber. Wir zeichnen dasselbe mit
**Cairo** (eine Grafikbibliothek) in PNG-Dateien und lassen das AppIndicator-Symbol
zwischen diesen Bildern wechseln, um die Animation nachzubilden.

Da die GNOME-Leiste dunkel ist, zeichnen wir die Streifen hell (weiß). Das Status-
Abzeichen bekommt eine Farbe (rot = Aufnahme, gelb = Verarbeitung, grün = fertig,
rot = Fehler), damit man den Zustand auf einen Blick erkennt.
"""

from __future__ import annotations

import math
from pathlib import Path

import cairo

from ..services.settings_store import DATA_DIR
from ..state import MenuBarStatus, StatusKind

_ICON_SIZE = 44  # Pixel; AppIndicator skaliert auf die Panel-Höhe herunter.
_STRIPE_WIDTHS = [1.0, 0.83, 0.66, 0.5]  # relative Breiten (12,10,8,6 wie im Original)

# Farben der Status-Abzeichen (R, G, B).
_BADGE_COLORS = {
    StatusKind.RECORDING: (0.93, 0.27, 0.24),   # rot
    StatusKind.PROCESSING: (0.98, 0.69, 0.16),  # gelb/orange
    StatusKind.SUCCESS: (0.30, 0.78, 0.36),     # grün
    StatusKind.ERROR: (0.93, 0.27, 0.24),       # rot
}


class TrayIconRenderer:
    """Erzeugt die PNG-Frames und verwaltet einen Ordner mit den Bildern."""

    def __init__(self) -> None:
        # Nicht /tmp: die (snap-verpackte) GNOME-Shell kann /tmp-Pfade nicht lesen.
        self._dir = DATA_DIR / "icons"
        self._dir.mkdir(parents=True, exist_ok=True)
        self.theme_path = str(self._dir)  # AppIndicator sucht Icons nach Name in diesem Ordner
        # Pro Status 4 Animations-Frames als PNG in den Ordner schreiben.
        for kind in StatusKind:
            for frame in range(4):
                self._render(kind, frame)

    def frame_name(self, status: MenuBarStatus, frame: int) -> str:
        """Icon-Name ohne .png-Endung (das erwartet AppIndicator.set_icon_full)."""
        return f"{status.kind.value}_{frame % 4}"

    def is_animated(self, status: MenuBarStatus) -> bool:
        return status.kind in (StatusKind.RECORDING, StatusKind.PROCESSING)

    # MARK: - Zeichnen ---------------------------------------------------------

    def _render(self, kind: StatusKind, frame: int) -> None:
        size = _ICON_SIZE
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        ctx = cairo.Context(surface)

        self._draw_stripes(ctx, size, kind, frame)
        if kind in _BADGE_COLORS:
            self._draw_badge(ctx, size, kind, frame)

        surface.write_to_png(str(self._dir / f"{kind.value}_{frame}.png"))

    def _draw_stripes(self, ctx: cairo.Context, size: int, kind: StatusKind, frame: int) -> None:
        stripe_h = size * 0.11
        spacing = size * 0.09
        total_h = len(_STRIPE_WIDTHS) * stripe_h + (len(_STRIPE_WIDTHS) - 1) * spacing
        origin_y = (size - total_h) / 2
        max_w = size * 0.66

        alphas = self._stripe_alphas(kind, frame)
        for i, rel_w in enumerate(_STRIPE_WIDTHS):
            w = max_w * rel_w
            x = (size - w) / 2
            y = origin_y + i * (stripe_h + spacing)
            self._rounded_rect(ctx, x, y, w, stripe_h, stripe_h / 2)
            ctx.set_source_rgba(1, 1, 1, alphas[i])  # weiß
            ctx.fill()

    def _draw_badge(self, ctx: cairo.Context, size: int, kind: StatusKind, frame: int) -> None:
        r, g, b = _BADGE_COLORS[kind]
        badge_r = size * 0.18
        cx = size - badge_r - size * 0.04
        cy = size - badge_r - size * 0.04

        # Pulsierende Deckkraft bei Aufnahme/Verarbeitung.
        if kind in (StatusKind.RECORDING, StatusKind.PROCESSING):
            alpha = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(frame / 4 * 2 * math.pi))
        else:
            alpha = 1.0

        ctx.arc(cx, cy, badge_r, 0, 2 * math.pi)
        ctx.set_source_rgba(r, g, b, alpha)
        ctx.fill()

    def _stripe_alphas(self, kind: StatusKind, frame: int) -> list[float]:
        # Bei Aufnahme/Verarbeitung "wandert" die Helligkeit durch die Streifen (wie im Original).
        if kind in (StatusKind.RECORDING, StatusKind.PROCESSING):
            base = [0.35, 0.55, 0.75, 1.0]
            return base[-frame % 4:] + base[: -frame % 4] if frame else base
        if kind is StatusKind.SUCCESS:
            return [1.0, 0.9, 0.78, 0.62]
        if kind is StatusKind.ERROR:
            return [1.0, 0.7, 0.52, 0.36]
        return [1.0, 0.82, 0.64, 0.46]  # idle

    @staticmethod
    def _rounded_rect(ctx: cairo.Context, x: float, y: float, w: float, h: float, r: float) -> None:
        r = min(r, w / 2, h / 2)
        ctx.new_sub_path()
        ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        ctx.close_path()
