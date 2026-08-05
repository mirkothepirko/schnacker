"""Gemeinsames für die beiden OpenAI-Aufrufe (Whisper und Chat Completions).

Bisher stand die Fehler-Auswertung wortgleich in transcription.py und llm.py.
Damit sich beide nie auseinanderentwickeln, steht sie jetzt nur hier.
"""

from __future__ import annotations

import requests


def error_message(response: requests.Response) -> str:
    """Liest die Fehlermeldung aus der JSON-Antwort; sonst der Statuscode."""
    try:
        message = response.json().get("error", {}).get("message")
    except ValueError:
        message = None
    return str(message) if message else f"Status {response.status_code}"
