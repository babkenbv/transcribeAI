# transcribeAI: live Armenian → English for calls

Listens to your microphone and your computer's audio output at the same time,
transcribes spoken Armenian, translates it to English and prints it in the
terminal, labelled by speaker. Everything runs locally on CPU.

```
[00:00:20] Speaker 1  HY: Այն օգտագործում է արբանյակի վրա հիմնված տեխնոլոգիա...
                      EN: It uses satellite-based technology, unlike the old ground-based radar technology.
                      (7.0s audio, 3.2s latency: wait 1.15 asr 0.74 spk 0.55 mt 0.74)
[00:00:34] Me         HY: Լավ եմ, շնորհակալություն։
                      EN: I'm fine, thank you.
```

The grey line shows the segment length, the latency from end of speech to the printed line,
and where that time went (`wait` = pause detection + queueing). Hide it with `--hide-latency`.

## Setup (Linux, tested on Linux Mint 21.3 / PulseAudio)

Requirements: Python 3.10, `ffmpeg`, PulseAudio or PipeWire-pulse (`parec`, `pactl`), ~3 GB disk.

```bash
pip install --user uv                 # if python3-venv is missing
uv venv -p 3.10 .venv
uv pip install -p .venv -r requirements.txt \
    --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match
scripts/convert_mt.sh                 # downloads NLLB-200 600M, converts to CTranslate2 int8 (models/)
```

The ASR, speaker and VAD models are downloaded automatically on first run (~600 MB).

### Audio devices

```bash
.venv/bin/python main.py --list-devices
```

- **Microphone**: your input source, for example `alsa_input....analog-stereo`.
- **System audio**: the *monitor* of the output your call plays on, for example
  `alsa_output....analog-stereo.monitor`. You still hear the call normally.
  **The output must not be muted**, because the monitor of a muted sink is silent.

With no flags, the default source and the monitor of the default sink are used.
If the call runs through headphones or a USB headset, pick that sink's monitor:

```bash
.venv/bin/python main.py --mic <source> --system <sink>.monitor
```

**macOS (not tested):** install BlackHole 2ch and create a Multi-Output Device
(speakers + BlackHole) in Audio MIDI Setup, then set it as the output. Pass the
device indices from `--list-devices` as `--mic N --system M`.

### Run

```bash
.venv/bin/python main.py                       # mic + system audio
.venv/bin/python main.py --no-mic              # only the other side
.venv/bin/python main.py --file call16k.wav    # replay a 16 kHz wav as the system side
```

Loading takes ~50 s. Ctrl+C stops.

## Models: what and why

All numbers are measured on this laptop (i7-8565U, 4 cores, no GPU) with the scripts in `eval/`.
The full reasoning is in [DECISIONS.md](DECISIONS.md).

| Part | Chosen | Alternatives measured / considered |
|---|---|---|
| ASR | **NVIDIA FastConformer hybrid hy** (115 M, CTC head): FLEURS dev WER 8.7 %, CER 3.8 %, RTF 0.045 | whisper-small Armenian fine-tune: WER 35.0 %, RTF 0.53. Whisper large-v3-turbo fine-tunes, MMS-1b, SeamlessM4T: too slow on CPU |
| Translation | **NLLB-200 distilled 600M**, CTranslate2 int8, beam 1: chrF 62.3, BLEU 35.9, ~1 s / sentence | beam 2: +1 chrF, +0.3 s. NLLB 1.3B / MADLAD 3B: over the latency budget |
| Speakers | **TitaNet-large** embeddings + online centroid clustering (cos ≥ 0.35) | thresholds 0.3–0.7 and min-duration 1–3 s swept on LibriSpeech |
| VAD | **Silero VAD** | (standard choice, small and fast) |

Armenian is low-resource, and the decisive factor was finding an ASR model trained on a
meaningful amount of Armenian that is also small. The NVIDIA model is both. Whisper models,
even fine-tuned, are much weaker on Armenian and much slower on CPU.

## Architecture

```
 mic ──parec──► Segmenter (Silero VAD) ──┐
                                          ├─► queue ─► worker: ASR → speaker label → MT → print
 monitor ─parec─► Segmenter (Silero VAD) ─┘
```

| File | Responsibility |
|---|---|
| `transcribe/audio.py` | device listing; 16 kHz mono capture via `parec` (Linux) or sounddevice; wav replay |
| `transcribe/segmenter.py` | cuts speech at pauses; force-cuts long speech at the quietest point |
| `transcribe/asr.py` | Armenian ASR (NeMo), plus a Whisper backend used only for comparison |
| `transcribe/translate.py` | hy → en with NLLB in CTranslate2 |
| `transcribe/speakers.py` | speaker embeddings and online clustering (`Me` for mic, `Speaker N` for system) |
| `transcribe/pipeline.py` | threads, queue, timing, output |
| `main.py` | CLI |
| `eval/` | ASR, MT, speaker and test-audio scripts |

One capture thread per source and **one** worker. Each model already uses all cores, and a
single worker keeps lines in order. A warning is printed if segments start queueing.

## Evaluation

```bash
# data (not committed): FLEURS hy_am dev (~200 MB) and LibriSpeech dev-clean (~340 MB)
mkdir -p data/fleurs && cd data/fleurs
curl -LO https://huggingface.co/datasets/google/fleurs/resolve/main/data/hy_am/dev.tsv && mv dev.tsv hy_dev.tsv
curl -L https://huggingface.co/datasets/google/fleurs/resolve/main/data/en_us/dev.tsv -o en_dev.tsv
curl -L https://huggingface.co/datasets/google/fleurs/resolve/main/data/hy_am/audio/dev.tar.gz | tar xz
cd .. && curl -L https://www.openslr.org/resources/12/dev-clean.tar.gz | tar xz && cd ..

.venv/bin/python -m eval.asr_eval --limit 60
.venv/bin/python -m eval.mt_eval --model models/nllb-200-distilled-600M-ct2
.venv/bin/python -m eval.speaker_eval --k 2 3 4 --thresholds 0.3 0.35 0.4
.venv/bin/python -m eval.make_conversation && .venv/bin/python main.py --file data/conversation.wav
```

Test checklist: [TESTS.md](TESTS.md).

## Measured results

- **Latency**, end of speech → line: 1.2–4.3 s in live tests. Short conversational phrases
  take ~1.2 s. Long read-speech monologues (FLEURS, ~11 s per sentence with no pauses)
  take 2–4.3 s because they get force-cut and queue behind each other.
- **ASR**: 8.7 % WER on FLEURS dev. Expect worse on spontaneous speech (see limitations).
- **Speakers**: on synthetic 2–4 speaker conversations, 98–100 % of segments labelled correctly.
  The right number of speakers was found in 70–90 % of trials. The typical error is one extra label.

## Known limitations

- **Evaluation data is read speech.** The ASR model saw FLEURS train during training, so 8.7 % is
  optimistic. Spontaneous, colloquial or dialectal Armenian, and code-switching with
  Russian/English, will be worse. A small set of real conversational recordings with transcripts
  is the most important missing piece.
- **Latency has little headroom on long monologues** (max 4.3 s seen). A video call app running
  on the same CPU can push it over 5 s. The backlog warning shows when that happens.
- **Speaker clustering** is tuned on English LibriSpeech, not Armenian call audio. Compressed call
  audio and similar voices will cause extra labels or, more rarely, merges. Labels are never revised
  after printing. A short first utterance (< 1 s) from a new person goes to an existing speaker.
- **Overlapping speech** on the system side gets one label and a mixed transcript.
- **Segments are translated independently**, so a sentence force-cut at 8 s is translated in two halves.
- **No echo handling** (out of scope): if the speakers are loud, the mic hears the other side and
  it is printed again as `Me`. Use headphones.
- macOS / Windows paths (sounddevice) are written but untested.

## With more time

1. Record ~30 min of real Armenian conversation with transcripts, and re-measure WER and speaker accuracy on it.
2. Run translation on the previous segment + the current one (context) and print only the new part.
3. Re-cluster speakers in the background and correct labels retroactively. Use pyannote-style overlap detection.
4. Export ASR to ONNX / use int8 to cut ASR and speaker time and leave more headroom.
5. Test on macOS with BlackHole.

## AI chat transcripts

`chats/`: every session used for this project, exported unedited as Markdown.
