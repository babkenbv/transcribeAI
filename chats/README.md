# AI chat transcripts

Every AI session used for this project, one Markdown file per session.

| File | Session | What happened |
|---|---|---|
| [01-session-6b04fbb6-build.md](01-session-6b04fbb6-build.md) | `6b04fbb6-be3a-4d40-a39b-30d9d6cc0cae` | Planning, research, model evaluation, building and testing the app, first live run, short-phrase translation fix, and a first attempt at this export that was blocked by the app's safety filter |
| [02-session-bd066139-resumed.md](02-session-bd066139-resumed.md) | `bd066139-865f-4f99-ad20-deb92e2735cf` | The same conversation resumed from an earlier point (it repeats session 1 up to the fork), then the requirements check and this export |

## How these files were made

All sessions ran in **Claude Code** (desktop app, Code tab). The app stores each session as a
`.jsonl` file under `~/.claude/projects/-home-babken-Projects-transcribeAI/`.
[`scripts/export_chats.py`](../scripts/export_chats.py) converts each file to Markdown:

```bash
python3 scripts/export_chats.py ~/.claude/projects/-home-babken-Projects-transcribeAI/<id>.jsonl chats/<name>.md
```

**Included, unedited and in order:** every user message (also those sent while the assistant
was working), every assistant reply, every tool call with its full input, every tool result,
and the app's notices (errors, refusals, model switches).

**Not included:** records that are not part of the visible conversation. These are the model's
hidden reasoning blocks, the system-prompt snapshot, API request logs, tool and skill listings,
file-history snapshots and account metadata.

The original sessions are still in the app, as the brief asks.
