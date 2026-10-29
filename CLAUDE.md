# Project rules

- Python 3.10, venv in `.venv` (created with `uv`). CPU only.
- Keep modules separate: audio, segmentation, ASR, translation, speakers, pipeline.
- Fail loudly. No silent fallbacks, no broad `except`, no hidden retries.
- Don't add features beyond the brief (see PLAN.md). Make the core reliable first.
- Every model choice is backed by a number from `eval/` and recorded in DECISIONS.md.
- Never commit model weights, audio (`data/`), or keys.
- Commit after every working step.
