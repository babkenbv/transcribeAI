"""Translation quality + speed on FLEURS hy→en dev (reference Armenian text in).

    python -m eval.mt_eval --model models/nllb-200-distilled-600M-ct2 --limit 100

This measures MT alone on clean input. End-to-end quality also depends on ASR errors.
"""
import argparse
import time

import sacrebleu

from eval.fleurs import english_refs, load_hy
from transcribe.translate import Translator


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--beam", type=int, default=2)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--show", type=int, default=5)
    args = ap.parse_args()

    en = english_refs()
    seen, pairs = set(), []
    for u in load_hy():
        if u.id in en and u.id not in seen:
            seen.add(u.id)
            pairs.append((u.text, en[u.id]))
    pairs = pairs[: args.limit]

    mt = Translator(args.model, beam_size=args.beam)
    mt.translate(pairs[0][0])  # warm-up

    hyps, times = [], []
    for i, (hy, ref) in enumerate(pairs):
        t0 = time.perf_counter()
        hyps.append(mt.translate(hy))
        times.append(time.perf_counter() - t0)
        if i < args.show:
            print(f"HY : {hy}\nREF: {ref}\nHYP: {hyps[-1]}\n")
    refs = [p[1] for p in pairs]
    times.sort()
    print(f"sentences: {len(pairs)}")
    print(f"chrF: {sacrebleu.corpus_chrf(hyps, [refs]).score:.1f}  BLEU: {sacrebleu.corpus_bleu(hyps, [refs]).score:.1f}")
    print(f"per-sentence p50: {times[len(times)//2]:.2f}s  max: {times[-1]:.2f}s")


if __name__ == "__main__":
    main()
