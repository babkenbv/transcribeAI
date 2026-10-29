"""Armenian → English translation with CTranslate2 (int8 on CPU).

Models are converted once with `scripts/convert_mt.sh` into models/<name>/.
Two model families are supported, recognised by their tokenizer files:
  - NLLB-200 (`sentencepiece.bpe.model`): `hye_Armn <pieces> </s>` in, `eng_Latn <pieces>` out
  - Marian / opus-mt (`source.spm`, `target.spm`): `<pieces> </s>` in, `<pieces>` out
"""
from pathlib import Path

import ctranslate2
import sentencepiece as spm

DEFAULT_MT_MODEL = "models/nllb-200-distilled-600M-ct2"
SRC_LANG, TGT_LANG = "hye_Armn", "eng_Latn"


class Translator:
    def __init__(self, model_dir: str = DEFAULT_MT_MODEL, beam_size: int = 1, threads: int = 4):
        path = Path(model_dir)
        if not (path / "model.bin").exists():
            raise FileNotFoundError(f"{path}/model.bin not found: run scripts/convert_mt.sh first")
        self.is_nllb = (path / "sentencepiece.bpe.model").exists()
        if self.is_nllb:
            self.src_sp = self.tgt_sp = spm.SentencePieceProcessor(
                model_file=str(path / "sentencepiece.bpe.model"))
        else:
            self.src_sp = spm.SentencePieceProcessor(model_file=str(path / "source.spm"))
            self.tgt_sp = spm.SentencePieceProcessor(model_file=str(path / "target.spm"))
        self.model = ctranslate2.Translator(
            str(path), device="cpu", compute_type="int8", intra_threads=threads
        )
        self.beam_size = beam_size

    def translate(self, text: str) -> str:
        if not text.strip():
            return ""
        tokens = self.src_sp.encode(text, out_type=str) + ["</s>"]
        if self.is_nllb:
            tokens = [SRC_LANG] + tokens
        result = self.model.translate_batch(
            [tokens], target_prefix=[[TGT_LANG]] if self.is_nllb else None,
            beam_size=self.beam_size, max_decoding_length=256,
        )[0]
        out = result.hypotheses[0]
        return self.tgt_sp.decode(out[1:] if self.is_nllb else out)  # drop the eng_Latn token


DEFAULT_SHORT_MT_MODEL = "models/opus-mt-hy-en-ct2"


class RoutedTranslator:
    """Very short utterances → opus-mt, everything else → NLLB.

    NLLB was trained on sentences and invents text for 1–2 word inputs
    ("Ողջույն։" → "I'm going to be a little late."). opus-mt (partly trained on
    subtitles) handles those well but is much worse on full sentences.
    Measured in eval/short_eval.py and eval/mt_eval.py, see DECISIONS.md D3.
    """

    def __init__(self, main: Translator, short: Translator, max_short_words: int = 2):
        self.main = main
        self.short = short
        self.max_short_words = max_short_words

    def translate(self, text: str) -> str:
        if len(text.split()) <= self.max_short_words:
            return self.short.translate(text)
        return self.main.translate(text)
