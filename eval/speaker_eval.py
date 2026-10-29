"""Online speaker clustering on synthetic conversations from LibriSpeech dev-clean.

FLEURS has no speaker IDs, so we use LibriSpeech (English, 40 speakers). Speaker
embeddings are largely language-independent, but the result is only a proxy for
Armenian calls (also: clean read speech, not compressed call audio).

For each trial: pick K speakers, interleave `turns` utterances of them in random
order (cropped to 1–8 s like VAD segments), run the online clusterer and score:
  - accuracy: fraction of segments whose label maps to the right speaker
    (each predicted label → its majority true speaker)
  - found: number of labels created (ideal = K)

    python -m eval.speaker_eval --k 2 3 4 --thresholds 0.4 0.5 0.6
"""
import argparse
import random
from collections import Counter
from pathlib import Path

import numpy as np
import soundfile as sf

from transcribe.speakers import OnlineClusterer, SpeakerEmbedder

LIBRI = Path(__file__).resolve().parent.parent / "data" / "LibriSpeech" / "dev-clean"


def load_utterances(per_speaker: int, rng: random.Random) -> dict[str, list[np.ndarray]]:
    out = {}
    for spk in sorted(p.name for p in LIBRI.iterdir()):
        files = sorted((LIBRI / spk).rglob("*.flac"))
        rng.shuffle(files)
        clips = []
        for f in files[:per_speaker]:
            x, sr = sf.read(f, dtype="float32")
            assert sr == 16000
            n = int(rng.uniform(1.0, 8.0) * sr)
            clips.append(x[:n])
        out[spk] = clips
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, nargs="+", default=[2, 3, 4])
    ap.add_argument("--thresholds", type=float, nargs="+", default=[0.35, 0.45, 0.55, 0.65])
    ap.add_argument("--min-new", type=float, nargs="+", default=[1.0, 2.0])
    ap.add_argument("--trials", type=int, default=10)
    ap.add_argument("--turns", type=int, default=24)
    args = ap.parse_args()

    rng = random.Random(0)
    per_speaker = args.turns
    data = load_utterances(per_speaker, rng)
    cache_file = LIBRI.parent / f"embeddings_{per_speaker}.npz"
    keys = [(s, i) for s, clips in data.items() for i in range(len(clips))]
    if cache_file.exists():
        stored = np.load(cache_file)
        cache = {k: stored[f"{k[0]}_{k[1]}"] for k in keys}
    else:
        emb = SpeakerEmbedder()
        print("embedding clips…")
        cache = {(s, i): emb.embed(data[s][i]) for s, i in keys}
        np.savez(cache_file, **{f"{s}_{i}": v for (s, i), v in cache.items()})
    durs = {(s, i): len(c) / 16000 for s, clips in data.items() for i, c in enumerate(clips)}

    speakers = sorted(data)
    print(f"{'K':>2} {'min_new':>7} {'thr':>5} {'accuracy':>9} {'found(mean)':>12} {'exact K':>8}")
    for k in args.k:
        trials = []
        for _ in range(args.trials):
            spk = rng.sample(speakers, k)
            seq = [(rng.choice(spk), rng.randrange(per_speaker)) for _ in range(args.turns)]
            trials.append(seq)
        for min_new, thr in [(m, t) for m in args.min_new for t in args.thresholds]:
            accs, found = [], []
            for seq in trials:
                cl = OnlineClusterer(threshold=thr, min_new_speaker_s=min_new)
                pred = [cl.assign(cache[key], durs[key]) for key in seq]
                true = [key[0] for key in seq]
                majority = {p: Counter(t for t, q in zip(true, pred) if q == p).most_common(1)[0][0]
                            for p in set(pred)}
                accs.append(np.mean([majority[p] == t for p, t in zip(pred, true)]))
                found.append(len(set(pred)))
            exact = np.mean([f == k for f in found])
            print(f"{k:>2} {min_new:>7.1f} {thr:>5.2f} {np.mean(accs):>9.2%} {np.mean(found):>12.1f} {exact:>8.0%}")


if __name__ == "__main__":
    main()
