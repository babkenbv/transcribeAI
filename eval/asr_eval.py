"""ASR accuracy + speed on FLEURS hy_am dev.

    python -m eval.asr_eval --backend nemo --limit 60
    python -m eval.asr_eval --backend whisper --model models/whisper-small-hy-ct2 --limit 60

Text is normalised (lowercase, punctuation stripped) before WER/CER so that
punctuation style differences between models don't count as errors.
"""
import argparse
import re
import time

import jiwer

from eval.fleurs import load_hy, read_audio
from transcribe.asr import NemoASR, WhisperASR

# Armenian punctuation: ։ (full stop), ՝ (comma), ՞ (question), ՜ (exclamation), « » quotes, plus ASCII.
_PUNCT = re.compile(r"[^\w\s]|_", re.UNICODE)


def normalise(text: str) -> str:
    text = text.lower().replace("և", "եւ")
    return " ".join(_PUNCT.sub(" ", text).split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["nemo", "whisper"], default="nemo")
    ap.add_argument("--model", help="model name/path (default per backend)")
    ap.add_argument("--decoder", default="ctc", help="nemo only: ctc or rnnt")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--show", type=int, default=5, help="print this many hyp/ref pairs")
    args = ap.parse_args()

    if args.backend == "nemo":
        asr = NemoASR(**({"model_name": args.model} if args.model else {}), decoder=args.decoder)
    else:
        asr = WhisperASR(args.model)

    utts = load_hy(args.limit)
    asr.transcribe(read_audio(utts[0].path))  # warm-up, excluded from timing

    refs, hyps, audio_s, compute_s, per_utt = [], [], 0.0, 0.0, []
    for i, u in enumerate(utts):
        samples = read_audio(u.path)
        t0 = time.perf_counter()
        hyp = asr.transcribe(samples)
        dt = time.perf_counter() - t0
        audio_s += len(samples) / 16000
        compute_s += dt
        per_utt.append(dt)
        refs.append(normalise(u.text))
        hyps.append(normalise(hyp))
        if i < args.show:
            print(f"REF: {u.text}\nHYP: {hyp}\n    ({len(samples)/16000:.1f}s audio, {dt:.2f}s)\n")

    per_utt.sort()
    print(f"utterances: {len(utts)}  audio: {audio_s:.0f}s")
    print(f"WER: {jiwer.wer(refs, hyps)*100:.1f}%  CER: {jiwer.cer(refs, hyps)*100:.1f}%")
    print(f"RTF: {compute_s/audio_s:.3f}  "
          f"per-utt p50: {per_utt[len(per_utt)//2]:.2f}s  max: {per_utt[-1]:.2f}s  "
          f"(avg utt {audio_s/len(utts):.1f}s)")


if __name__ == "__main__":
    main()
