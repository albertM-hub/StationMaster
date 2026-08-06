"""
dax_audio.py — Capture/lecture audio via les devices PipeWire "DAX" exposés par
AetherSDR (aethersdr-dax-1..4 en RX, aethersdr-tx en TX), pour l'onglet SSTV.

Contexte (voir docs/plans/2026-08-06-sstv-tab-design.md) : le protocole TCI
d'AetherSDR ne livre pas de flux audio binaire exploitable sur ce déploiement —
l'audio transite en réalité par ces devices audio système PipeWire, créés par la
fonctionnalité DAX (même principe que le DAX de SmartSDR/FlexRadio).

Deux pièges rencontrés en test réel, à ne pas réintroduire :
- L'API bloquante `sounddevice.rec()`/`.wait()` reste bloquée indéfiniment sur
  ces devices DAX dans cet environnement → toujours utiliser l'API par callback
  (`sd.InputStream`/`sd.OutputStream`), comme fait ici.
- L'index PortAudio d'un device DAX change d'une exécution à l'autre (observé :
  aethersdr-dax-1 à l'index 1 puis 19) → toujours résoudre le device par son
  nom via `find_device()`, jamais par un index codé en dur.
"""

import queue
import threading

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 48000


def find_device(name_substring, kind="input"):
    """Résout l'index PortAudio d'un device par sous-chaîne de nom.

    Ne jamais coder un index en dur : il change d'une exécution à l'autre.
    """
    for i, d in enumerate(sd.query_devices()):
        if name_substring in d["name"]:
            if kind == "input" and d["max_input_channels"] > 0:
                return i
            if kind == "output" and d["max_output_channels"] > 0:
                return i
    return None


class DAXAudioRX:
    """Capture continue depuis un device DAX (RX) vers une queue de blocs
    numpy float32 mono, consommée par sstv_decoder."""

    def __init__(
        self, device_name="aethersdr-dax-1", samplerate=SAMPLE_RATE, blocksize=2048
    ):
        self.device_name = device_name
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.audio_queue = queue.Queue()
        self._stream = None

    @property
    def running(self):
        return self._stream is not None

    def start(self):
        idx = find_device(self.device_name, kind="input")
        if idx is None:
            raise RuntimeError(f"Device DAX introuvable (RX) : {self.device_name}")
        self._stream = sd.InputStream(
            device=idx,
            channels=1,
            samplerate=self.samplerate,
            dtype="float32",
            blocksize=self.blocksize,
            callback=self._callback,
        )
        self._stream.start()

    def _callback(self, indata, frames, time_info, status):
        self.audio_queue.put(indata[:, 0].copy())

    def stop(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None


class DAXAudioTX:
    """Lecture d'un tableau de samples vers le device TX DAX (aethersdr-tx)."""

    def __init__(self, device_name="aethersdr-tx", samplerate=SAMPLE_RATE):
        self.device_name = device_name
        self.samplerate = samplerate
        self._stop_flag = threading.Event()

    def play(self, samples: np.ndarray, blocksize=2048):
        """Bloquant : joue `samples` en entier (ou jusqu'à stop()). À appeler
        depuis un thread dédié, jamais depuis le thread Tkinter."""
        idx = find_device(self.device_name, kind="output")
        if idx is None:
            raise RuntimeError(f"Device DAX introuvable (TX) : {self.device_name}")
        self._stop_flag.clear()
        samples = samples.astype("float32", copy=False)
        pos = 0

        def callback(outdata, frames, time_info, status):
            nonlocal pos
            if self._stop_flag.is_set() or pos >= len(samples):
                outdata.fill(0)
                raise sd.CallbackStop()
            chunk = samples[pos : pos + frames]
            outdata[: len(chunk), 0] = chunk
            if len(chunk) < frames:
                outdata[len(chunk) :, 0] = 0
            pos += len(chunk)

        with sd.OutputStream(
            device=idx,
            channels=1,
            samplerate=self.samplerate,
            dtype="float32",
            blocksize=blocksize,
            callback=callback,
        ) as stream:
            while stream.active and not self._stop_flag.is_set():
                sd.sleep(50)

    def stop(self):
        self._stop_flag.set()


if __name__ == "__main__":
    import argparse
    import time
    import wave

    parser = argparse.ArgumentParser(
        description="Capture de test depuis un device DAX RX, sauvegarde en WAV."
    )
    parser.add_argument("--device", default="aethersdr-dax-1")
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--out", default="dax_capture.wav")
    args = parser.parse_args()

    rx = DAXAudioRX(device_name=args.device)
    rx.start()
    print(f"[dax_audio] Capture {args.duration}s depuis {args.device}...")

    blocks = []
    start = time.time()
    while time.time() - start < args.duration:
        try:
            blocks.append(rx.audio_queue.get(timeout=0.5))
        except queue.Empty:
            pass
    rx.stop()

    data = np.concatenate(blocks) if blocks else np.array([], dtype="float32")
    rms = float(np.sqrt(np.mean(data**2))) if data.size else 0.0
    print(f"[dax_audio] {data.size} échantillons capturés, RMS={rms:.5f}")

    pcm16 = np.clip(data * 32767, -32768, 32767).astype("int16")
    with wave.open(args.out, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm16.tobytes())
    print(f"[dax_audio] Sauvegardé dans {args.out}")
