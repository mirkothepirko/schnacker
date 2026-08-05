"""Mikrofon-Aufnahme — Ersatz für AudioRecorder.swift.

Statt AVAudioRecorder nutzen wir `sounddevice` (Zugriff aufs Mikrofon über
PortAudio/PipeWire). Wir nehmen wie das Original mit 16 kHz, mono auf und
schreiben am Ende eine WAV-Datei (die OpenAI-Whisper und faster-whisper direkt lesen).

`sounddevice` ruft unsere `_callback`-Funktion fortlaufend in einem eigenen
Thread (Nebenstrang) auf und liefert dort kleine Audio-Häppchen. Diese sammeln
wir ein und berechnen nebenbei den Lautstärke-Pegel für die Wellenform-Anzeige.
"""

from __future__ import annotations

import math
import threading
import uuid
import wave
from pathlib import Path
from tempfile import gettempdir

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000  # Hz — wie im Original (AVSampleRateKey: 16000)
CHANNELS = 1         # mono


class AudioRecorder:
    def __init__(self) -> None:
        self.is_recording = False
        self.recording_path: Path | None = None
        self.error_message: str | None = None
        self.audio_level: float = 0.0           # 0..1 für die Wellenform
        self.last_recording_duration: float = 0.0

        self._stream: sd.InputStream | None = None
        self._frames: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._current_path: Path | None = None

    def _make_recording_path(self) -> Path:
        return Path(gettempdir()) / f"blablatext-{uuid.uuid4()}.wav"

    # MARK: - Aufnahme-Callback (läuft im Audio-Thread) -----------------------

    def _callback(self, indata, frames, time_info, status):  # noqa: ARG002
        # indata ist ein numpy-Array mit Audio-Werten zwischen -1 und 1.
        with self._lock:
            self._frames.append(indata.copy())

        # Pegel berechnen: RMS -> Dezibel -> auf 0..1 normiert (wie (power+50)/50 im Original).
        rms = float(np.sqrt(np.mean(np.square(indata)))) if indata.size else 0.0
        power_db = 20.0 * math.log10(rms) if rms > 1e-9 else -160.0
        normalized = max(0.0, min(1.0, (power_db + 50.0) / 50.0))
        self.audio_level = normalized

    # MARK: - Steuerung -------------------------------------------------------

    def start_recording(self) -> None:
        self.error_message = None
        self.last_recording_duration = 0.0
        self.recording_path = None
        with self._lock:
            self._frames = []

        if self._current_path:
            self._current_path.unlink(missing_ok=True)

        try:
            self._current_path = self._make_recording_path()
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                callback=self._callback,
            )
            self._stream.start()
            self.is_recording = True
        except Exception as exc:  # noqa: BLE001 — wir wollen jede Audiopanne melden
            self._current_path = None
            self.error_message = f"Aufnahme konnte nicht gestartet werden: {exc}"

    def stop_recording(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        self.is_recording = False
        self.audio_level = 0.0

        with self._lock:
            frames = list(self._frames)
            self._frames = []

        total_samples = sum(len(f) for f in frames)
        self.last_recording_duration = total_samples / SAMPLE_RATE if total_samples else 0.0

        if total_samples == 0 or self._current_path is None:
            self.recording_path = None
            return

        audio = np.concatenate(frames, axis=0)
        self._write_wav(self._current_path, audio)
        self.recording_path = self._current_path
        self._current_path = None

    def discard_recording(self) -> None:
        if self.recording_path:
            self.recording_path.unlink(missing_ok=True)
            self.recording_path = None
        if self._current_path:
            self._current_path.unlink(missing_ok=True)
            self._current_path = None

    # MARK: - WAV schreiben ---------------------------------------------------

    @staticmethod
    def _write_wav(path: Path, audio: np.ndarray) -> None:
        """Schreibt die float-Audiodaten als 16-Bit-PCM-WAV (Standardformat)."""
        clipped = np.clip(audio, -1.0, 1.0)
        int16 = (clipped * 32767.0).astype(np.int16)
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(CHANNELS)
            wav.setsampwidth(2)  # 16 Bit = 2 Byte
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(int16.tobytes())
