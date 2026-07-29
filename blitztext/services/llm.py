"""OpenAI Chat Completions (Text umschreiben) — portiert aus LLMService.swift.

Zwei Aufgaben: Text verbessern (improve) und in Mundart übersetzen
(dampf_ablassen = Platt, basel_deutsch = Baseldütsch). Modelle, Temperaturen und
der Lektorats-Prompt sind wörtlich aus dem Original übernommen.
"""

from __future__ import annotations

import requests

from . import keychain
from ..models import TextImprovementSettings, TextTone

CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
TIMEOUT_SECONDS = 45

# Modelle wie im Original (enum RewriteModel).
MODEL_FAST_EDIT = "gpt-4o-mini"  # Verbessern
MODEL_RAGE = "gpt-4o"            # Schnacker Platt (kräftiges Modell für Dialekt-Übersetzung)


class LLMError(Exception):
    """Fehler bei der KI-Umschreibung. Nachricht ist deutsch/nutzerlesbar."""


# MARK: - Öffentliche Funktionen ----------------------------------------------


def improve(text: str, settings: TextImprovementSettings, model: str = MODEL_FAST_EDIT) -> str:
    return _complete(text, _build_system_prompt(settings), model, temperature=0.3)


def dampf_ablassen(text: str, system_prompt: str, model: str = MODEL_RAGE) -> str:
    return _complete(text, system_prompt, model, temperature=0.4)


def basel_deutsch(text: str, system_prompt: str, model: str = MODEL_RAGE) -> str:
    """Übersetzt Hochdeutsch -> Baseldütsch (Schnacker Basel)."""
    return _complete(text, system_prompt, model, temperature=0.4)


# MARK: - HTTP-Aufruf ---------------------------------------------------------


def _complete(text: str, system_prompt: str, model: str, temperature: float) -> str:
    api_key = keychain.load(keychain.KeychainKey.OPEN_AI_API_KEY)
    if not api_key:
        raise LLMError("OpenAI API Key fehlt. Bitte in den Einstellungen hinterlegen.")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "temperature": temperature,
    }

    try:
        response = requests.post(
            CHAT_COMPLETIONS_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise LLMError(f"Verbindungsproblem: {exc}") from exc

    if response.status_code != 200:
        raise LLMError(f"Fehler von OpenAI: {_error_message(response)}")

    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        content = None

    if not content or not content.strip():
        raise LLMError("Keine Antwort erhalten. Bitte nochmal versuchen.")
    return content.strip()


def _error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
        message = payload.get("error", {}).get("message")
        if message:
            return str(message)
    except ValueError:
        pass
    return f"Status {response.status_code}"


# MARK: - Prompt-Bau (wörtlich aus dem Original) ------------------------------


def _build_system_prompt(settings: TextImprovementSettings) -> str:
    # Eigene Anweisung gesetzt? Dann diese verwenden (+ ggf. Eigennamen-Zeile).
    if settings.system_prompt:
        prompt = settings.system_prompt
        if settings.custom_terms:
            prompt += (
                "\n\nWichtig: Diese Eigennamen und Fachbegriffe muessen exakt so geschrieben "
                f"werden: {', '.join(settings.custom_terms)}"
            )
        return prompt

    prompt = (
        "Du bist ein Lektor und Schreibassistent. Verbessere den folgenden Text:\n"
        "- Korrigiere Rechtschreibung und Grammatik\n"
        "- Verbessere die Formulierung und den Lesefluss\n"
        "- Behalte die urspruengliche Bedeutung bei\n"
        "- Gib NUR den verbesserten Text zurueck, keine Erklaerungen"
    )

    prompt += {
        TextTone.FORMAL: "\n- Verwende einen formellen, professionellen Ton",
        TextTone.NEUTRAL: "\n- Verwende einen neutralen, klaren Ton",
        TextTone.CASUAL: "\n- Verwende einen lockeren, natuerlichen Ton",
    }[settings.tone]

    if settings.custom_terms:
        prompt += (
            "\n\nWichtig: Diese Eigennamen und Fachbegriffe muessen exakt so geschrieben "
            f"werden: {', '.join(settings.custom_terms)}"
        )

    if settings.context:
        prompt += f"\n\nKontext: {settings.context}"

    return prompt
