"""Tastenkürzel-Zuordnung (Linux/GNOME-Ersatz für die fn-Kürzel des Originals).

Unter Wayland kann die App keine globalen Tastenkürzel selbst abfangen. Statt
dessen legen wir GNOME-Systemkürzel an, die das Kommando `python -m blitztext
--trigger <workflow>` aufrufen. Hier stehen die Standard-Kürzel und ihre Zuordnung.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .models import WorkflowType

# Anzeige-Label (im UI) -> wie im Original, nur mit Linux-Tasten.
SUGGESTED_LABEL: dict[WorkflowType, str] = {
    WorkflowType.TRANSCRIPTION: "Strg+Alt+1",
    WorkflowType.TEXT_IMPROVER: "Strg+Alt+2",
    WorkflowType.DAMPF_ABLASSEN: "Strg+Alt+3",
    WorkflowType.EMOJI_TEXT: "Strg+Alt+4",
}

# Form, die GNOME/gsettings für Tastenkombinationen erwartet.
GSETTINGS_BINDING: dict[WorkflowType, str] = {
    WorkflowType.TRANSCRIPTION: "<Control><Alt>1",
    WorkflowType.TEXT_IMPROVER: "<Control><Alt>2",
    WorkflowType.DAMPF_ABLASSEN: "<Control><Alt>3",
    WorkflowType.EMOJI_TEXT: "<Control><Alt>4",
}


def label_for(t: WorkflowType) -> str:
    """Kürzel-Text für die Workflow-Zeile (z.B. 'Super+1')."""
    return SUGGESTED_LABEL.get(t, "")


def trigger_arg(t: WorkflowType) -> str:
    """Argument für `--trigger`, das einen Workflow auslöst (= sein interner Name)."""
    return t.value


def install_gnome_shortcuts() -> str:
    """Legt Strg+Alt+1..4 als GNOME-Systemkürzel an (via gsettings).

    Jedes Kürzel ruft `python -m blitztext --trigger <workflow>` auf, was die
    laufende App über den Socket erreicht und den Workflow startet/stoppt.
    """
    project_dir = Path(__file__).resolve().parents[1]
    python = sys.executable
    base_schema = "org.gnome.settings-daemon.plugins.media-keys"
    item_schema = f"{base_schema}.custom-keybinding"
    base_path = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"

    def gset(schema_with_path: str, key: str, value: str) -> None:
        subprocess.run(["gsettings", "set", schema_with_path, key, value], check=True)

    try:
        paths: list[str] = []
        for i, t in enumerate(WorkflowType.main_menu_cases()):
            kb_path = f"{base_path}blitztext{i}/"
            paths.append(kb_path)
            command = (f"bash -c 'cd {project_dir} && "
                       f"{python} -m blitztext --trigger {trigger_arg(t)}'")
            gset(f"{item_schema}:{kb_path}", "name", f"Blitztext: {t.display_name}")
            gset(f"{item_schema}:{kb_path}", "command", command)
            gset(f"{item_schema}:{kb_path}", "binding", GSETTINGS_BINDING[t])

        value = "[" + ", ".join(f"'{p}'" for p in paths) + "]"
        subprocess.run(["gsettings", "set", base_schema, "custom-keybindings", value], check=True)
        return "Kürzel Strg+Alt+1 bis Strg+Alt+4 wurden eingerichtet."
    except (subprocess.SubprocessError, OSError) as exc:
        return f"Kürzel konnten nicht eingerichtet werden: {exc}"
