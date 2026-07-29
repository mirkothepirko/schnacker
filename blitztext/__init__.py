"""Schnacker für Ubuntu — Sprache zu Text in der Menüleiste.

Eine funktionsgleiche Neuimplementierung der macOS-App Blitztext für
Ubuntu/GNOME/Wayland. Aufbau spiegelt das Original (siehe original-reference/):

    models.py            -> WorkflowProtocol.swift (Typen & Einstellungen)
    state.py             -> AppState.swift (zentraler Zustand)
    app.py               -> BlitztextMacApp.swift (Tray + Fenster + Socket)
    services/            -> Services/ (Aufnahme, OpenAI, lokal, Schlüsselbund, Paste)
    workflows/           -> Features/Workflows/
    ui/                  -> Features/MenuBar/ + Views/
"""