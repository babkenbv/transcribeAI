"""Armenian speech recognition.

Default: NVIDIA FastConformer hybrid (Transducer + CTC) trained on ~296 h of Armenian.
See DECISIONS.md for why this model and why the CTC head.
"""
import logging

import numpy as np

DEFAULT_ASR_MODEL = "nvidia/stt_hy_fastconformer_hybrid_large_pc"


class NemoASR:
    def __init__(self, model_name: str = DEFAULT_ASR_MODEL, decoder: str = "ctc"):
        # NeMo logs to stdout at INFO level; keep stdout for transcripts.
        from nemo.utils import logging as nemo_logging
        nemo_logging.setLevel(logging.ERROR)
        from nemo.collections.asr.models import ASRModel

        self.model = ASRModel.from_pretrained(model_name, map_location="cpu")
        self.model.eval()
        if decoder not in ("ctc", "rnnt"):
            raise ValueError(f"decoder must be 'ctc' or 'rnnt', got {decoder!r}")
        # NeMo suggests 'greedy_batch' for CTC; measured no gain for batch size 1 (DECISIONS.md D2).
        self.model.change_decoding_strategy(decoder_type=decoder, verbose=False)

    def transcribe(self, samples: np.ndarray) -> str:
        """samples: 16 kHz mono float32 in [-1, 1]."""
        out = self.model.transcribe([samples.astype(np.float32)], batch_size=1, verbose=False)
        # Hybrid models return a list of Hypothesis objects (or a tuple of lists for RNNT).
        if isinstance(out, tuple):
            out = out[0]
        hyp = out[0]
        return (hyp.text if hasattr(hyp, "text") else hyp).strip()


class WhisperASR:
    """faster-whisper backend. Used for comparison in eval/, not the default."""

    def __init__(self, model_path: str, beam_size: int = 1):
        from faster_whisper import WhisperModel

        self.model = WhisperModel(model_path, device="cpu", compute_type="int8")
        self.beam_size = beam_size

    def transcribe(self, samples: np.ndarray) -> str:
        segments, _ = self.model.transcribe(
            samples.astype(np.float32),
            language="hy",
            beam_size=self.beam_size,
            vad_filter=False,
            condition_on_previous_text=False,
        )
        return " ".join(s.text.strip() for s in segments).strip()
