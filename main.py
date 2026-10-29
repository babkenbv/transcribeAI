"""Live Armenian → English transcription of mic + system audio.

    python main.py --list-devices
    python main.py                                  # PulseAudio defaults
    python main.py --mic <source> --system <monitor source>
    python main.py --file call.wav                  # replay a file as the system side
"""
import argparse
import os
import sys
import time
import warnings

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
warnings.filterwarnings("ignore")


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list-devices", action="store_true", help="print input devices and exit")
    ap.add_argument("--mic", help="microphone device (default: system default source)")
    ap.add_argument("--system", help="system-audio device, e.g. <sink>.monitor (default: monitor of default sink)")
    ap.add_argument("--no-mic", action="store_true", help="only listen to system audio")
    ap.add_argument("--no-system", action="store_true", help="only listen to the microphone")
    ap.add_argument("--file", help="replay a 16 kHz wav in real time as the system side (for testing)")
    ap.add_argument("--asr-decoder", default="ctc", choices=["ctc", "rnnt"])
    ap.add_argument("--mt-model", default=None, help="CTranslate2 model dir")
    ap.add_argument("--speaker-threshold", type=float, default=None, help="cosine similarity for same speaker")
    ap.add_argument("--hide-latency", action="store_true")
    return ap.parse_args()


def main():
    args = parse_args()
    from transcribe import audio

    if args.list_devices:
        for d in audio.list_devices():
            tag = "  [system audio / monitor]" if d.is_monitor else ""
            print(f"{d.id}\n    {d.description}{tag}")
        return

    devices = {}
    if args.file:
        devices["system"] = "file:" + args.file
    else:
        if args.mic is None or args.system is None:
            default_mic, default_sys = audio.default_devices()
        if not args.no_mic:
            devices["mic"] = args.mic or default_mic
        if not args.no_system:
            devices["system"] = args.system or default_sys
        if not devices:
            sys.exit("nothing to listen to: --no-mic and --no-system both set")
        for dev in devices.values():
            audio.check_device(dev)

    print("loading models (first run downloads them)…", file=sys.stderr, flush=True)
    t = time.time()
    from transcribe.asr import NemoASR
    from transcribe.pipeline import Pipeline
    from transcribe.speakers import OnlineClusterer, SpeakerEmbedder
    from transcribe.translate import DEFAULT_MT_MODEL, Translator

    asr = NemoASR(decoder=args.asr_decoder)
    translator = Translator(args.mt_model or DEFAULT_MT_MODEL)
    embedder = SpeakerEmbedder()
    clusterer = OnlineClusterer(**({"threshold": args.speaker_threshold} if args.speaker_threshold else {}))
    pipe = Pipeline(asr, translator, embedder, clusterer, show_latency=not args.hide_latency)
    pipe.warm_up()
    print(f"models loaded in {time.time() - t:.0f}s", file=sys.stderr)

    for src, dev in devices.items():
        print(f"  {src:<7} ← {dev}", file=sys.stderr)
    print("listening. Ctrl+C to stop.\n", file=sys.stderr, flush=True)
    pipe.run(devices)


if __name__ == "__main__":
    main()
