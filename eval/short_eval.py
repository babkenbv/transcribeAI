"""Translation of short conversational phrases (eval/short_phrases.tsv, hand-written).

FLEURS only has long read sentences. On a call many utterances are 1–3 words,
where NLLB is known to hallucinate. This prints every output side by side and
chrF per word-count bucket for each model.

    python -m eval.short_eval models/nllb-200-distilled-600M-ct2 models/opus-mt-hy-en-ct2
"""
import argparse
from pathlib import Path

import sacrebleu

from transcribe.translate import Translator

PHRASES = Path(__file__).resolve().parent / "short_phrases.tsv"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="+")
    args = ap.parse_args()

    pairs = [l.rstrip("\n").split("\t") for l in PHRASES.read_text(encoding="utf-8").splitlines() if l.strip()]
    outs = {m: [Translator(m).translate(hy) for hy, _ in pairs] for m in args.models}
    names = [Path(m).name[:22] for m in args.models]

    for i, (hy, ref) in enumerate(pairs):
        cols = "  ".join(f"{outs[m][i][:30]:<30}" for m in args.models)
        print(f"{hy[:28]:<28} {ref[:24]:<24} {cols}")

    buckets = {"1 word": lambda n: n == 1, "2 words": lambda n: n == 2, "3+ words": lambda n: n >= 3}
    print(f"\n{'chrF':<10}" + "".join(f"{n:>24}" for n in names))
    for label, fits in buckets.items():
        idx = [i for i, (hy, _) in enumerate(pairs) if fits(len(hy.split()))]
        scores = [sacrebleu.corpus_chrf([outs[m][i] for i in idx], [[pairs[i][1] for i in idx]]).score
                  for m in args.models]
        print(f"{label + f' ({len(idx)})':<10}" + "".join(f"{s:>24.1f}" for s in scores))


if __name__ == "__main__":
    main()
