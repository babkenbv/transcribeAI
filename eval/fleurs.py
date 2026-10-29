"""Load the FLEURS hy_am dev split from data/fleurs (see README for the download commands)."""
import csv
from dataclasses import dataclass
from pathlib import Path

import soundfile as sf

FLEURS_DIR = Path(__file__).resolve().parent.parent / "data" / "fleurs"


@dataclass
class Utterance:
    id: int
    path: Path
    text: str  # raw transcription with punctuation
    gender: str


def _read_tsv(path: Path) -> list[list[str]]:
    with open(path, encoding="utf-8") as f:
        return list(csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE))


def load_hy(limit: int | None = None) -> list[Utterance]:
    rows = _read_tsv(FLEURS_DIR / "hy_dev.tsv")
    utts = [
        Utterance(int(r[0]), FLEURS_DIR / "dev" / r[1], r[2], r[6])
        for r in rows
    ]
    # FLEURS has several recordings per sentence; sort for a deterministic subset.
    utts.sort(key=lambda u: (u.id, u.path.name))
    return utts[:limit] if limit else utts


def english_refs() -> dict[int, str]:
    """Sentence id -> English reference text (FLEURS is n-way parallel by id)."""
    return {int(r[0]): r[2] for r in _read_tsv(FLEURS_DIR / "en_dev.tsv")}


def read_audio(path: Path):
    samples, sr = sf.read(path, dtype="float32")
    if sr != 16000:
        raise ValueError(f"{path}: expected 16 kHz, got {sr}")
    return samples
