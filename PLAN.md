# Plan

## Goal
Live Armenian speech → Armenian text + English translation in the terminal,
labelled by speaker (`Me` for the mic, `Speaker N` for system audio),
≤ 5 s from end of phrase to printed line. Local models only, Python.

## Target machine
Linux Mint 21.3, PulseAudio, Intel i7-8565U (4C/8T, 2018 laptop CPU), 11 GB RAM,
no usable GPU (MX250 with no driver loaded). Everything must run on CPU, so model size is the
main constraint.

## Modules (input → output)

| Module | Input | Output |
|---|---|---|
| `audio.py` | device name / index | stream of 16 kHz mono float32 blocks per source |
| `segmenter.py` | audio blocks | `Segment(source, t_start, t_end, samples)` cut at pauses (Silero VAD) |
| `asr.py` | segment samples | Armenian text |
| `translate.py` | Armenian text | English text |
| `speakers.py` | segment samples (system source only) | stable label `Speaker N` |
| `pipeline.py` | segments | printed lines + latency |
| `main.py` | CLI flags | wires everything together, `--list-devices` |

Threads: one capture+VAD thread per source → one shared queue → one worker
(ASR → speaker → MT → print). One worker keeps the 4 CPU cores from being
split between competing model calls.

## Steps
1. Walking skeleton: file → VAD → ASR → MT → print (no live audio yet).
2. Evaluation scripts on FLEURS hy_am dev: ASR WER/CER + real-time factor,
   MT chrF/BLEU against the parallel FLEURS en_us sentences. Compare candidates.
3. Live capture of mic + monitor source; segmenter; latency printed per line.
4. Speaker embeddings + online clustering for the system-audio side; test
   on a synthetic multi-speaker stream built from FLEURS speakers.
5. README, limitations.

## Risks
- CPU latency: ASR + MT must fit in ~3 s after VAD's end-of-speech wait.
- Armenian model quality (low-resource).
- Speaker clustering on short segments is unstable.
- PortAudio on Linux cannot pick a PulseAudio monitor source directly → use `parec`.

## Testing
See `TESTS.md`.
