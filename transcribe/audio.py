"""Audio capture: yields 16 kHz mono float32 blocks of BLOCK samples from one device.

Linux (PulseAudio / PipeWire-pulse): we read via `parec`, because PortAudio's ALSA
backend only exposes a single "pulse" device and cannot open a specific source
such as the monitor of the speakers (= the other side of a call).
Other OSes: sounddevice (PortAudio). On macOS the system audio comes from a
loopback device such as BlackHole.
"""
import queue
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Iterator

import numpy as np

SAMPLE_RATE = 16000
BLOCK = 512  # 32 ms, the chunk size Silero VAD expects at 16 kHz


@dataclass
class Device:
    id: str  # what you pass on the command line
    description: str
    is_monitor: bool = False


def use_pulse() -> bool:
    return sys.platform.startswith("linux") and shutil.which("parec") is not None and shutil.which("pactl") is not None


def list_devices() -> list[Device]:
    if use_pulse():
        out = subprocess.run(["pactl", "list", "sources"], capture_output=True, text=True, check=True).stdout
        devices, name = [], None
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("Name:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("Description:") and name:
                devices.append(Device(name, line.split(":", 1)[1].strip(), name.endswith(".monitor")))
                name = None
        return devices
    import sounddevice as sd

    return [
        Device(str(i), f"{d['name']} ({d['max_input_channels']} ch)")
        for i, d in enumerate(sd.query_devices())
        if d["max_input_channels"] > 0
    ]


def default_devices() -> tuple[str, str]:
    """(mic, system-audio monitor) defaults on PulseAudio."""
    if not use_pulse():
        raise RuntimeError("no defaults outside PulseAudio: pass --mic and --system (see --list-devices)")
    info = subprocess.run(["pactl", "info"], capture_output=True, text=True, check=True).stdout
    fields = dict(l.split(":", 1) for l in info.splitlines() if ":" in l)
    return fields["Default Source"].strip(), fields["Default Sink"].strip() + ".monitor"


def check_device(device_id: str) -> None:
    ids = [d.id for d in list_devices()]
    if device_id not in ids:
        listing = "\n  ".join(ids)
        raise SystemExit(f"Unknown audio device {device_id!r}. Available:\n  {listing}")


def capture(device_id: str, stop) -> Iterator[tuple[np.ndarray, float]]:
    """Yield (block, wall_time_at_end_of_block) until stop.is_set().

    "file:<path>" replays a 16 kHz mono wav at real-time speed (for testing).
    """
    if device_id.startswith("file:"):
        yield from _capture_file(device_id[5:], stop)
    elif use_pulse():
        yield from _capture_pulse(device_id, stop)
    else:
        yield from _capture_sounddevice(int(device_id), stop)


def _capture_file(path: str, stop):
    import soundfile as sf

    samples, sr = sf.read(path, dtype="float32", always_2d=True)
    if sr != SAMPLE_RATE:
        raise ValueError(f"{path}: expected {SAMPLE_RATE} Hz, got {sr} (convert with ffmpeg -ar 16000 -ac 1)")
    samples = samples.mean(axis=1)
    start = time.time()
    for i in range(0, len(samples) - BLOCK + 1, BLOCK):
        if stop.is_set():
            return
        t_due = start + (i + BLOCK) / SAMPLE_RATE
        time.sleep(max(0.0, t_due - time.time()))
        yield samples[i:i + BLOCK], time.time()
    # one second of silence so the segmenter closes the last segment
    for _ in range(round(SAMPLE_RATE / BLOCK)):
        time.sleep(BLOCK / SAMPLE_RATE)
        yield np.zeros(BLOCK, dtype=np.float32), time.time()


def _capture_pulse(device_id: str, stop):
    proc = subprocess.Popen(
        ["parec", f"--device={device_id}", "--format=float32le", f"--rate={SAMPLE_RATE}",
         "--channels=1", "--latency-msec=30", "--raw"],
        stdout=subprocess.PIPE,
        start_new_session=True,  # Ctrl+C goes to Python only; we stop parec ourselves
    )
    nbytes = BLOCK * 4
    try:
        while not stop.is_set():
            buf = proc.stdout.read(nbytes)
            if len(buf) < nbytes:
                raise RuntimeError(f"parec for {device_id!r} stopped (exit code {proc.poll()})")
            yield np.frombuffer(buf, dtype=np.float32).copy(), time.time()
    finally:
        proc.terminate()
        proc.wait()


def _capture_sounddevice(index: int, stop):
    import sounddevice as sd

    q: queue.Queue = queue.Queue()

    def callback(indata, frames, t, status):
        if status:
            print(f"[audio {index}] {status}", file=sys.stderr)
        q.put((indata[:, 0].copy(), time.time()))

    with sd.InputStream(device=index, channels=1, samplerate=SAMPLE_RATE, blocksize=BLOCK,
                        dtype="float32", callback=callback):
        while not stop.is_set():
            try:
                yield q.get(timeout=0.5)
            except queue.Empty:
                continue
