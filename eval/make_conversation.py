"""Build a test wav: FLEURS hy utterances separated by short pauses.

    python -m eval.make_conversation --n 12 --out data/conversation.wav

Replay it with `python main.py --file data/conversation.wav` to check end-to-end
latency and output. Reference texts are written next to it (.txt).
"""
import argparse
import random

import numpy as np
import soundfile as sf

from eval.fleurs import load_hy, read_audio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--pause", type=float, default=0.8)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="data/conversation.wav")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    utts = rng.sample(load_hy(), args.n)
    gap = np.zeros(int(args.pause * 16000), dtype=np.float32)
    parts, lines, t = [gap], [], args.pause
    for u in utts:
        x = read_audio(u.path)
        lines.append(f"[{t:6.1f}s] {u.text}")
        parts += [x, gap]
        t += len(x) / 16000 + args.pause
    sf.write(args.out, np.concatenate(parts), 16000)
    with open(args.out.rsplit(".", 1)[0] + ".txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {args.out} ({t:.0f}s, {args.n} utterances)")


if __name__ == "__main__":
    main()
