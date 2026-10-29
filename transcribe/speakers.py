"""Speaker labels for the system-audio side: TitaNet embeddings + online clustering.

Each segment's embedding is compared (cosine) with the running centroid of every
speaker seen so far. Above `threshold` → that speaker; otherwise a new speaker,
but only if the segment is long enough to trust its embedding. Short segments
that match nobody go to the closest existing speaker.
"""
import logging

import numpy as np
import torch

DEFAULT_SPK_MODEL = "nvidia/speakerverification_en_titanet_large"


class SpeakerEmbedder:
    def __init__(self, model_name: str = DEFAULT_SPK_MODEL, max_seconds: float = 4.0):
        # Longer input barely changes the embedding but costs time linearly
        # (measured in eval/speaker_eval.py, see DECISIONS.md).
        self.max_samples = int(max_seconds * 16000)
        from nemo.utils import logging as nemo_logging
        nemo_logging.setLevel(logging.ERROR)
        from nemo.collections.asr.models import EncDecSpeakerLabelModel

        self.model = EncDecSpeakerLabelModel.from_pretrained(model_name, map_location="cpu")
        self.model.eval()

    @torch.no_grad()
    def embed(self, samples: np.ndarray) -> np.ndarray:
        if len(samples) > self.max_samples:  # keep the middle part
            start = (len(samples) - self.max_samples) // 2
            samples = samples[start:start + self.max_samples]
        audio = torch.from_numpy(samples.astype(np.float32)).unsqueeze(0)
        length = torch.tensor([audio.shape[1]])
        _, emb = self.model.forward(input_signal=audio, input_signal_length=length)
        emb = emb.squeeze(0).numpy()
        return emb / np.linalg.norm(emb)


class OnlineClusterer:
    def __init__(self, threshold: float = 0.35, min_new_speaker_s: float = 1.0):
        self.threshold = threshold
        self.min_new_speaker_s = min_new_speaker_s
        self.sums: list[np.ndarray] = []  # unnormalised sum of member embeddings

    def assign(self, emb: np.ndarray, duration: float) -> int:
        """Return a 0-based speaker index."""
        if self.sums:
            centroids = np.stack([s / np.linalg.norm(s) for s in self.sums])
            sims = centroids @ emb
            best = int(np.argmax(sims))
            if sims[best] >= self.threshold or duration < self.min_new_speaker_s:
                self.sums[best] += emb
                return best
        self.sums.append(emb.copy())
        return len(self.sums) - 1
