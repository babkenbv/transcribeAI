#!/usr/bin/env bash
# Convert Hugging Face translation models to CTranslate2 int8 under models/.
# Usage: scripts/convert_mt.sh [hf-model-id ...]
# Default: NLLB-200 distilled 600M (main) and opus-mt-hy-en (1-2 word utterances).
set -euo pipefail
cd "$(dirname "$0")/.."
if [ $# -gt 0 ]; then models=("$@"); else models=(facebook/nllb-200-distilled-600M Helsinki-NLP/opus-mt-hy-en); fi
for m in "${models[@]}"; do
  out="models/$(basename "$m")-ct2"
  if [ -f "$out/model.bin" ]; then echo "exists: $out"; continue; fi
  case "$m" in
    *opus-mt*) files=(source.spm target.spm) ;;
    *) files=(sentencepiece.bpe.model) ;;
  esac
  .venv/bin/ct2-transformers-converter --model "$m" --output_dir "$out" \
    --quantization int8 --copy_files "${files[@]}"
  echo "converted: $out"
done
