"""Cut a stream of audio blocks into speech segments at pauses, using Silero VAD.

A segment ends when:
  - there has been `min_silence` of non-speech (normal end of a phrase), or
  - it is longer than `soft_len` and there is a short pause of `soft_silence`
    (keeps long monologues flowing without waiting for a full stop), or
  - it reaches `max_len`: then we cut at the least speech-like block in the last
    `cut_window` seconds (most likely a gap between words) and carry the rest
    over into the next segment, so words are not chopped in half.
"""
from collections import deque
from dataclasses import dataclass

import numpy as np
import torch
from silero_vad import load_silero_vad

from transcribe.audio import BLOCK, SAMPLE_RATE

BLOCK_S = BLOCK / SAMPLE_RATE


@dataclass
class Segment:
    source: str  # "mic" or "system"
    t_start: float  # wall clock, start of speech
    t_end: float  # wall clock, end of speech (latency is measured from here)
    samples: np.ndarray

    @property
    def duration(self) -> float:
        return len(self.samples) / SAMPLE_RATE


def _blocks(seconds: float) -> int:
    return round(seconds / BLOCK_S)


class Segmenter:
    def __init__(self, source: str, threshold: float = 0.5, min_silence: float = 0.5,
                 soft_len: float = 4.0, soft_silence: float = 0.2, max_len: float = 8.0,
                 cut_window: float = 2.0, min_speech: float = 0.4, pad: float = 0.2):
        self.source = source
        self.model = load_silero_vad()
        self.threshold = threshold
        self.neg_threshold = threshold - 0.15  # hysteresis, as in Silero's own iterator
        self.min_silence = _blocks(min_silence)
        self.soft_len = _blocks(soft_len)
        self.soft_silence = _blocks(soft_silence)
        self.max_len = _blocks(max_len)
        self.cut_window = _blocks(cut_window)
        self.min_speech = _blocks(min_speech)
        self.pad = _blocks(pad)
        self.preroll: deque = deque(maxlen=self.pad)
        self._reset()

    def _reset(self):
        self.active = False
        self.blocks: list[np.ndarray] = []
        self.probs: list[float] = []
        self.times: list[float] = []
        self.silence_run = 0

    def speech_prob(self, block: np.ndarray) -> float:
        with torch.no_grad():
            return self.model(torch.from_numpy(block), SAMPLE_RATE).item()

    def push(self, block: np.ndarray, t: float) -> Segment | None:
        """Feed one BLOCK (ending at wall time t); returns a Segment when one is complete."""
        p = self.speech_prob(block)
        if not self.active:
            self.preroll.append((block, t))
            if p >= self.threshold:
                self.active = True
                self.blocks = [b for b, _ in self.preroll]
                self.times = [bt for _, bt in self.preroll]
                self.probs = [0.0] * (len(self.blocks) - 1) + [p]
                self.preroll.clear()
            return None

        self.blocks.append(block)
        self.probs.append(p)
        self.times.append(t)
        self.silence_run = 0 if p >= self.neg_threshold else self.silence_run + 1

        if self.silence_run >= self.min_silence:
            return self._emit(len(self.blocks) - self.silence_run + self.pad, end_of_speech=True)
        if len(self.blocks) >= self.soft_len and self.silence_run >= self.soft_silence:
            return self._emit(len(self.blocks) - self.silence_run + self.soft_silence // 2,
                              end_of_speech=False)
        if len(self.blocks) >= self.max_len:
            window = self.probs[-self.cut_window:]
            cut = len(self.blocks) - self.cut_window + int(np.argmin(window)) + 1
            return self._emit(cut, end_of_speech=False)
        return None

    def _emit(self, n: int, end_of_speech: bool) -> Segment | None:
        """Emit the first n blocks; keep the rest as the start of the next segment."""
        n = min(n, len(self.blocks))
        speech = sum(pr >= self.neg_threshold for pr in self.probs[:n])
        seg = None
        if speech >= self.min_speech:
            t_start = self.times[0] - BLOCK_S
            # end of speech = last block that still looked like speech
            last = max(i for i in range(n) if self.probs[i] >= self.neg_threshold)
            seg = Segment(self.source, t_start, self.times[last], np.concatenate(self.blocks[:n]))
        rest = (self.blocks[n:], self.probs[n:], self.times[n:])
        self._reset()
        if end_of_speech:
            self.model.reset_states()
        elif rest[0]:
            self.active = True
            self.blocks, self.probs, self.times = (list(x) for x in rest)
        return seg
