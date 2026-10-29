"""Armenian → English translation with NLLB-200 in CTranslate2 (int8 on CPU).

The model is converted once with `scripts/convert_mt.sh` into models/<name>/.
Tokenisation uses the model's SentencePiece file directly (NLLB format:
`hye_Armn <pieces> </s>` in, `eng_Latn <pieces>` out).
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
        self.sp = spm.SentencePieceProcessor(model_file=str(path / "sentencepiece.bpe.model"))
        self.model = ctranslate2.Translator(
            str(path), device="cpu", compute_type="int8", intra_threads=threads
        )
        self.beam_size = beam_size

    def translate(self, text: str) -> str:
        if not text.strip():
            return ""
        tokens = [SRC_LANG] + self.sp.encode(text, out_type=str) + ["</s>"]
        result = self.model.translate_batch(
            [tokens], target_prefix=[[TGT_LANG]], beam_size=self.beam_size,
            max_decoding_length=256,
        )[0]
        return self.sp.decode(result.hypotheses[0][1:])  # drop the eng_Latn token
