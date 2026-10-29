"""Export Claude Code session transcripts (.jsonl) to Markdown, one file per session.

    python3 scripts/export_chats.py <session.jsonl> <out.md> [--title TITLE]

Renders the conversation as shown in the app, in order and without shortening:
user messages (including messages queued while the assistant was working),
assistant replies, every tool call with its full input, every tool result,
and the app's notices (errors, refusals, /model switches).

Not rendered: records that are not part of the conversation. These are the
model's hidden reasoning blocks, the system-prompt snapshot, API request logs,
tool/skill listings, file-history snapshots and account metadata.
"""
import argparse
import json
import re
from pathlib import Path


def fence(text: str, lang: str = "") -> str:
    """Code block whose fence is longer than any backtick run inside the text."""
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    ticks = "`" * max(3, longest + 1)
    return f"{ticks}{lang}\n{text}\n{ticks}"


def result_text(content) -> str:
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if block.get("type") == "text":
            parts.append(block["text"])
        elif block.get("type") == "image":
            parts.append("[image]")
        else:
            parts.append(json.dumps(block, ensure_ascii=False))
    return "\n".join(parts)


def render(records: list[dict]) -> list[str]:
    out = []
    for r in records:
        kind = r.get("type")
        ts = (r.get("timestamp") or "")[:19].replace("T", " ")

        if kind == "user":
            content = r["message"]["content"]
            if isinstance(content, str):
                out.append(f"### 👤 User · {ts}\n\n{content}\n")
                continue
            for block in content:
                if block.get("type") == "text":
                    out.append(f"### 👤 User · {ts}\n\n{block['text']}\n")
                elif block.get("type") == "tool_result":
                    label = "Tool result (error)" if block.get("is_error") else "Tool result"
                    out.append(f"**{label}**\n\n{fence(result_text(block.get('content')))}\n")
                elif block.get("type") == "image":
                    out.append(f"### 👤 User · {ts}\n\n[image]\n")

        elif kind == "assistant":
            for block in r["message"]["content"]:
                if block.get("type") == "text" and block["text"].strip():
                    out.append(f"### 🤖 Assistant · {ts}\n\n{block['text']}\n")
                elif block.get("type") == "tool_use":
                    args = json.dumps(block.get("input", {}), ensure_ascii=False, indent=2)
                    out.append(f"**Tool call: `{block['name']}`**\n\n{fence(args, 'json')}\n")

        elif kind == "attachment" and r["attachment"].get("type") == "queued_command":
            prompt = r["attachment"].get("prompt")
            text = prompt if isinstance(prompt, str) else result_text(prompt)
            out.append(f"### 👤 User (sent while the assistant was working) · {ts}\n\n{text}\n")

        elif kind == "system" and r.get("content"):
            out.append(f"> **App notice** · {ts}: {r['content']}\n")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--title", default="")
    args = ap.parse_args()

    records = [json.loads(line) for line in args.jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    stamps = [r["timestamp"] for r in records if r.get("timestamp")]
    session_id = next(r["sessionId"] for r in records if r.get("sessionId"))
    header = [
        f"# {args.title or 'Claude Code session'}\n",
        f"- Session ID: `{session_id}`",
        f"- Tool: Claude Code (desktop app, Code tab)",
        f"- From {min(stamps)[:19].replace('T', ' ')} to {max(stamps)[:19].replace('T', ' ')} UTC",
        f"- Exported from `{args.jsonl.name}` with `scripts/export_chats.py`\n",
        "---\n",
    ]
    args.out.write_text("\n".join(header + render(records)), encoding="utf-8")
    print(f"wrote {args.out} ({args.out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
