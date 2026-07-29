"""OpenAI-Whisper-Transkription (online) — 1:1 portiert aus TranscriptionService.swift.

Schickt die Audiodatei per multipart/form-data an die OpenAI-API und bekommt
reinen Text zurück. Gleiche Parameter wie im Original: Modell `whisper-1`,
`response_format=text`, optionale `language` und `prompt` (Eigennamen), Timeout 60 s.
"""

from __future__ import annotations

from pathlib import Path

import requests

from . import keychain
from . import openai_api

REMOTE_MODEL = "whisper-1"
TRANSCRIPTIONS_URL = "https://api.openai.com/v1/audio/transcriptions"
TIMEOUT_SECONDS = 60


class TranscriptionError(Exception):
    """Fehler bei der Transkription. Die Nachricht ist bereits deutsch/nutzerlesbar."""


def transcribe(audio_path: Path, custom_terms: list[str] | None = None,
               language: str | None = None) -> str:
    api_key = keychain.load()
    if not api_key:
        raise TranscriptionError("OpenAI API Key fehlt. Bitte in den Einstellungen hinterlegen.")

    custom_terms = custom_terms or []

    # Felder des Formulars. `files` enthält die Audiodatei, `data` die Textfelder.
    data: dict[str, str] = {
        "model": REMOTE_MODEL,
        "response_format": "text",
    }
    if custom_terms:
        data["prompt"] = "Eigennamen und Begriffe: " + ", ".join(custom_terms)
    if language and language.strip():
        data["language"] = language.strip()

    try:
        with open(audio_path, "rb") as fh:
            files = {"file": ("audio.wav", fh, "audio/wav")}
            response = requests.post(
                TRANSCRIPTIONS_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "text/plain, application/json",
                },
                data=data,
                files=files,
                timeout=TIMEOUT_SECONDS,
            )
    except requests.RequestException as exc:
        raise TranscriptionError(f"Netzwerkfehler: {exc}") from exc

    if response.status_code != 200:
        raise TranscriptionError(f"OpenAI-Fehler: {openai_api.error_message(response)}")

    text = response.text.strip()
    if not text:
        raise TranscriptionError("OpenAI-Fehler: Transkription fehlgeschlagen")
    return text
