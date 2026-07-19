"""OpenAI-Whisper-Transkription (online) — 1:1 portiert aus TranscriptionService.swift.

Schickt die Audiodatei per multipart/form-data an die OpenAI-API und bekommt
reinen Text zurück. Gleiche Parameter wie im Original: Modell `whisper-1`,
`response_format=text`, optionale `language` und `prompt` (Eigennamen), Timeout 60 s.
"""

from __future__ import annotations

from pathlib import Path

import requests

from . import keychain

REMOTE_MODEL = "whisper-1"
TRANSCRIPTIONS_URL = "https://api.openai.com/v1/audio/transcriptions"
TIMEOUT_SECONDS = 60

# Firmeneigene Begriffe, die Whisper ohne Hinweis regelmäßig falsch erkennt.
# Werden unabhängig von den nutzerdefinierten Eigennamen (Einstellungen) immer mitgeschickt.
BUILT_IN_TERMS = ["Flötotto"]


class TranscriptionError(Exception):
    """Fehler bei der Transkription. Die Nachricht ist bereits deutsch/nutzerlesbar."""


def transcribe(audio_path: Path, custom_terms: list[str] | None = None,
               language: str | None = None) -> str:
    api_key = keychain.load(keychain.KeychainKey.OPEN_AI_API_KEY)
    if not api_key:
        raise TranscriptionError("OpenAI API Key fehlt. Bitte in den Einstellungen hinterlegen.")

    # Eingebaute Begriffe zuerst, danach die Eigennamen aus den Einstellungen
    # (Duplikate entfernen, Reihenfolge bleibt erhalten).
    terms = list(dict.fromkeys(BUILT_IN_TERMS + (custom_terms or [])))

    # Felder des Formulars. `files` enthält die Audiodatei, `data` die Textfelder.
    data: dict[str, str] = {
        "model": REMOTE_MODEL,
        "response_format": "text",
    }
    if terms:
        data["prompt"] = "Eigennamen und Begriffe: " + ", ".join(terms)
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
        raise TranscriptionError(f"OpenAI-Fehler: {_error_message(response)}")

    text = response.text.strip()
    if not text:
        raise TranscriptionError("OpenAI-Fehler: Transkription fehlgeschlagen")
    return text


def _error_message(response: requests.Response) -> str:
    """Versucht, die Fehlermeldung aus der JSON-Antwort zu lesen; sonst Statuscode."""
    try:
        payload = response.json()
        message = payload.get("error", {}).get("message")
        if message:
            return str(message)
    except ValueError:
        pass
    return f"Status {response.status_code}"
