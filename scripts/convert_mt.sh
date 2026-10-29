#!/usr/bin/env bash
# Convert Hugging Face translation models to CTranslate2 int8 under models/.
# Usage: scripts/convert_mt.sh [hf-model-id ...]   (default: NLLB-200 distilled 600M)
set -euo pipefail
cd "$(dirname "$0")/.."
models=("${@:-facebook/nllb-200-distilled-600M}")
for m in "${models[@]}"; do
  out="models/$(basename "$m")-ct2"
  if [ -f "$out/model.bin" ]; then echo "exists: $out"; continue; fi
  .venv/bin/ct2-transformers-converter --model "$m" --output_dir "$out" \
    --quantization int8 --copy_files tokenizer.json tokenizer_config.json special_tokens_map.json sentencepiece.bpe.model
  echo "converted: $out"
done
