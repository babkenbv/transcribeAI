"""Glue: capture threads → segment queue → one worker (ASR → speaker → MT → print).

One worker on purpose: on a 4-core CPU, running two model calls at once makes
both slower, and the queue keeps the lines in chronological order.
"""
import queue
import sys
import threading
import time
from dataclasses import dataclass

import numpy as np

from transcribe.audio import capture
from transcribe.segmenter import Segment, Segmenter


@dataclass
class Line:
    t_offset: float  # seconds since session start
    speaker: str
    hy: str
    en: str
    latency: float  # end of speech → line ready
    audio_s: float
    stages: dict[str, float]  # seconds spent per stage, incl. "wait" before processing started


def format_line(line: Line, show_latency: bool) -> str:
    h, rem = divmod(int(line.t_offset), 3600)
    m, s = divmod(rem, 60)
    out = f"[{h:02d}:{m:02d}:{s:02d}] {line.speaker:<10} HY: {line.hy}\n{'':<22}EN: {line.en}"
    if show_latency:
        stages = " ".join(f"{k} {v:.2f}" for k, v in line.stages.items())
        out += f"\n{'':<22}\033[2m({line.audio_s:.1f}s audio, {line.latency:.1f}s latency: {stages})\033[0m"
    return out


class Pipeline:
    def __init__(self, asr, translator, embedder, clusterer, show_latency=True):
        self.asr = asr
        self.translator = translator
        self.embedder = embedder
        self.clusterer = clusterer
        self.show_latency = show_latency
        self.segments: queue.Queue[Segment] = queue.Queue()
        self.stop = threading.Event()
        self.t0 = time.time()
        self.errors: queue.Queue[BaseException] = queue.Queue()
        self.busy = threading.Event()

    def warm_up(self):
        """Run each model once: the first call is several times slower than the rest."""
        noise = (np.random.default_rng(0).standard_normal(2 * 16000) * 0.01).astype(np.float32)
        self.asr.transcribe(noise)
        self.embedder.embed(noise)
        self.translator.translate("Բարեւ, ինչպե՞ս ես։")

    def label(self, seg: Segment) -> str:
        if seg.source == "mic":
            return "Me"
        idx = self.clusterer.assign(self.embedder.embed(seg.samples), seg.duration)
        return f"Speaker {idx + 1}"

    def process(self, seg: Segment) -> Line | None:
        t = time.time()
        stages = {"wait": t - seg.t_end}
        hy = self.asr.transcribe(seg.samples)
        stages["asr"] = time.time() - t
        if not hy:
            return None
        t = time.time()
        speaker = self.label(seg)
        stages["spk"] = time.time() - t
        t = time.time()
        en = self.translator.translate(hy)
        stages["mt"] = time.time() - t
        return Line(seg.t_start - self.t0, speaker, hy, en, time.time() - seg.t_end, seg.duration, stages)

    # --- threads -------------------------------------------------------------

    def _capture_loop(self, source: str, device_id: str):
        try:
            seg = Segmenter(source)
            for block, t in capture(device_id, self.stop):
                s = seg.push(block, t)
                if s is not None:
                    self.segments.put(s)
        except BaseException as e:  # surfaced in the main thread, not swallowed
            self.errors.put(e)
            self.stop.set()

    def _worker_loop(self):
        try:
            while not self.stop.is_set():
                try:
                    seg = self.segments.get(timeout=0.2)
                except queue.Empty:
                    continue
                self.busy.set()
                line = self.process(seg)
                if line is not None:
                    print(format_line(line, self.show_latency), flush=True)
                backlog = self.segments.qsize()
                if backlog >= 3:
                    print(f"\033[33m[warning] {backlog} segments waiting: CPU can't keep up\033[0m",
                          file=sys.stderr, flush=True)
                self.busy.clear()
        except BaseException as e:
            self.errors.put(e)
            self.stop.set()

    def run(self, devices: dict[str, str]):
        """devices: {"mic": id, "system": id}. Blocks until Ctrl+C or a thread fails."""
        captures = [threading.Thread(target=self._capture_loop, args=(src, dev), daemon=True)
                    for src, dev in devices.items()]
        threads = captures + [threading.Thread(target=self._worker_loop, daemon=True)]
        self.t0 = time.time()
        for t in threads:
            t.start()
        try:
            while not self.stop.is_set():
                time.sleep(0.2)
                # file replay: all input consumed and processed → done
                if (not any(t.is_alive() for t in captures)
                        and self.segments.empty() and not self.busy.is_set()):
                    break
        except KeyboardInterrupt:
            print("\nstopping…", file=sys.stderr)
        self.stop.set()
        for t in threads:
            t.join(timeout=2)
        if not self.errors.empty():
            raise self.errors.get()
