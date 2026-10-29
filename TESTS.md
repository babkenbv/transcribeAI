# Tests and QA checks

These come from the requirements in the brief, not from the code.

## Automated / scripted
- [x] `eval/asr_eval.py`: WER/CER and real-time factor on FLEURS hy_am dev (N utterances).
- [x] `eval/mt_eval.py`: chrF/BLEU on FLEURS hy→en dev reference pairs, plus seconds per sentence.
- [x] `eval/speaker_eval.py`: synthetic stream of utterances from K LibriSpeech speakers (FLEURS has no speaker IDs).
      Check that the number of labels equals K and measure label purity.
- [x] Latency: `eval/make_conversation.py` + `main.py --file data/conversation.wav` replays a wav
      in real time through the full pipeline. Per-line latency printed: 1.3–4.2 s.

## Manual (live, before the interview)
- [x] `--list-devices` shows the mic and the monitor source.
- [x] Speaking into the mic prints `Me` lines.
- [x] (via a virtual null sink + paplay) Playing Armenian audio prints `Speaker N` lines.
- [ ] Two different voices on the system side get two different labels, and each keeps its label.
- [x] Mic and system audio at the same time: both appear and neither blocks the other.
- [ ] The latency column stays under 5 s during a 5-minute conversation (no queue build-up).
- [x] Ctrl+C exits cleanly.
- [x] A wrong device name fails loudly with the list of valid devices.

## Status notes (2026-10-29)
- Mic tested only with room conversation picked up by the laptop mic (1.2 s latency), not a real call.
- Speaker labelling on real call audio with 2+ people is **not tested yet**. Do this before the interview.
- The 5-minute run with no queue build-up is **not tested yet**.
