# Decision log

All timings are on the target laptop: Intel i7-8565U (4 cores), CPU only.
Evaluation data: FLEURS hy_am dev (read speech) and LibriSpeech dev-clean (speakers).

## D1. Target: CPU only
The laptop's MX250 has no driver loaded and only 2 GB VRAM. Everything is
designed for CPU, so model size and speed decide most of the choices below.

## D2. ASR: NVIDIA FastConformer hybrid, Armenian (`nvidia/stt_hy_fastconformer_hybrid_large_pc`), CTC head
Measured on 60 FLEURS dev utterances (`eval/asr_eval.py`, punctuation stripped):

| Model | WER | CER | RTF | p50 per utt (avg 11.5 s) |
|---|---|---|---|---|
| **FastConformer hy, CTC** | **8.7 %** | **3.8 %** | **0.045** | **0.46 s** |
| whisper-small Armenian fine-tune (`Chillarmo/whisper-small-armenian-v2`, CT2 int8, beam 1) | 35.0 % | 13.3 % | 0.534 | 5.95 s |

- 115 M parameters and trained on ~296 h of Armenian (Common Voice 17, FLEURS, and others).
  It outputs punctuation and capitalisation.
- It is about 4× more accurate and 12× faster than the best Whisper fine-tune that fits the
  latency budget. Whisper large-v3(-turbo) Armenian fine-tunes were not tried: the turbo encoder
  alone is far over budget on this CPU.
- **Caveat:** FLEURS *train* is in its training data. Dev sentences are different, but the
  domain (read speech, similar mics) is the same, so 8.7 % is optimistic for conversation.
- The CTC head is used instead of RNNT for speed. Both run through `--asr-decoder`.
- NeMo recommends `greedy_batch` CTC decoding. Same WER, measured RTF 0.057 vs 0.045 (noise or
  thermal throttling, decoding is a tiny part of the cost), so the default was kept.
- Not evaluated: Meta MMS-1b-all (1 B params, no punctuation, slower) and SeamlessM4T v2
  (2.3 B, too slow on this CPU).

## D3. MT: NLLB-200 distilled 600M, CTranslate2 int8, beam 1
`eval/mt_eval.py`, 100 FLEURS hy→en dev sentences (avg ~20 words), reference Armenian input:

| Setting | chrF | BLEU | p50 | max |
|---|---|---|---|---|
| beam 1 | 62.3 | 35.9 | 1.03 s | 2.71 s |
| beam 2 | 63.3 | 36.6 | 1.30 s | 3.07 s |

- Beam 1: −1 chrF for −0.3 s. Latency headroom matters more because a video call also uses the CPU.
  `--mt-beam` is not exposed; change `Translator(beam_size=…)` if the machine is faster.
- Tokenisation uses the SentencePiece model directly. The transformers 5 tokenizer printed a
  "wrong regex" warning, and the direct version gives identical scores.
- NLLB 1.3B would be ~2× slower (max ≈ 5–6 s) and break the budget. MADLAD-400 3B is larger still.

### D3b. Short utterances → opus-mt-hy-en (added after the first live test)
Live test: "Ողջույն։" → "I'm going to be a little late." NLLB invents text for 1–2 word
input, and beam 4 doesn't fix it ("Ողջույն" → "How are you?"). FLEURS has no short phrases, so
`eval/short_phrases.tsv` was written by hand: 36 call phrases with references. It's small and
written by us, so treat it as indicative only. `eval/short_eval.py`, chrF:

| Words | NLLB 600M | opus-mt-hy-en | routed (≤2 → opus) |
|---|---|---|---|
| 1 (11) | 29.1 | 61.3 | 61.3 |
| 2 (11) | 63.6 | 82.4 | 82.4 |
| 3+ (14) | 71.5 | 51.6 | 71.5 |

opus-mt on FLEURS sentences: chrF 40.8 vs 62.3 for NLLB, so it is only used for ≤ 2 words.
It takes ~0.02 s per phrase and ~80 MB. Both still fail on some single words
("Ցտեսություն" → "Mr." with opus-mt, "I'll see you later" with NLLB).
NLLB 1.3B was not tried: not enough disk space left on this laptop.

## D4. VAD + segmentation: Silero VAD, cut at pauses
- A segment ends after 0.5 s of silence. Once longer than 4 s, a 0.2 s pause is enough.
- At 8 s it is force-cut at the least speech-like 32 ms block in the last 2 s, and the rest
  carries over. The first version hard-cut at exactly 8 s and chopped words in half
  ("տեղեկատվ|ություն"), which broke both ASR and MT for those words. After the change,
  no chopped words in the replay test.

## D5. Speakers: TitaNet-large embeddings + online centroid clustering
- Mic = `Me` by definition. Only the system side is clustered.
- Each segment's embedding (L2-normalised) is compared with the centroid of every speaker so far.
  Cosine ≥ threshold → that speaker, else a new one. A segment shorter than 1 s may not create a
  new speaker (its embedding is too noisy) and goes to the nearest one.
- Tuned with `eval/speaker_eval.py` on LibriSpeech dev-clean (FLEURS has no speaker IDs).
  K speakers, 24 turns, 20 trials:

| K | min_new | thr | accuracy | labels found (mean) | exactly K |
|---|---|---|---|---|---|
| 2 | 1.0 | 0.35 | 100 % | 2.1 | 90 % |
| 3 | 1.0 | 0.35 | 100 % | 3.2 | 80 % |
| 4 | 1.0 | 0.35 | 100 % | 4.2 | 75 % |
| 3 | 2.0 | 0.35 | 94.8 % | 3.0 | 75 % |
| 3 | 1.0 | 0.45 | 100 % | 3.7 | 45 % |

  → threshold 0.35, min_new 1.0 s. The typical error is an occasional extra label (one person
  split into two), not two people merged. Raising min_new causes merges, which is worse.
- On the FLEURS replay, labels matched the speakers' gender metadata 12/12.
- Caveat: LibriSpeech is English read speech and TitaNet saw LibriSpeech *train* speakers.
  Compressed call audio will lower similarities, and `--speaker-threshold` exists for that.
- Embedding input is cropped to the middle 4 s: TitaNet took ~0.7 s on 7 s segments, as long as ASR.
  With the crop, ~0.45 s. Re-running the eval at thr 0.35 gave K=2: 100 % / 90 % exact,
  K=3: 98.1 % / 70 %, K=4: 99.6 % / 85 %. About the same as uncropped, within 20-trial noise.

## D6. Audio capture on Linux via `parec`
PortAudio's ALSA backend only exposes one "pulse" device, so it can't open the monitor source
(= what the speakers play) and the mic at the same time. `parec --device=<source>` can.
On other OSes sounddevice is used, with BlackHole as the loopback device on macOS (untested).

## D7. One worker thread
ASR, speaker and MT run one after another in a single worker. Each already uses all 4 cores
internally, so running two at once would mostly split the same cores (not measured). It also keeps
lines in order. The worker prints a warning when segments queue up
(≥ 3 waiting), so falling behind is visible instead of silent.
