"""Count your real Claude Code token usage from its local logs.

Claude Code writes the same response to its logs several times, so a plain sum over-counts.
This keeps one record per response (message id + request id) with its final output count.
Reads ~/.claude/projects on Mac, Linux and Windows. Prints numbers only; sends nothing anywhere.
Usage:  python3 count_claude_code_tokens.py [path-to-projects-folder]
From https://neverpaytwice.com/claude-code-token-count
"""
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path.home() / ".claude" / "projects"
best, plain = {}, 0

for f in sorted(root.rglob("*.jsonl")):
    n = 0
    for line in f.open(encoding="utf-8", errors="replace"):
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if not isinstance(o, dict):
            continue
        n += 1
        m = o.get("message")
        if o.get("type") != "assistant" or not isinstance(m, dict) or not m.get("usage"):
            continue
        if m.get("model") == "<synthetic>" or o.get("isApiErrorMessage"):
            continue
        u = m["usage"]
        t = [u.get("input_tokens") or 0, u.get("output_tokens") or 0,
             u.get("cache_creation_input_tokens") or 0, u.get("cache_read_input_tokens") or 0]
        plain += sum(t)
        if m.get("id") or o.get("requestId"):
            key = (m.get("id") or "", o.get("requestId") or "")
        else:
            key = (str(f), n)
        if key not in best:
            best[key] = t
        else:
            best[key][1] = max(best[key][1], t[1])  # streaming: keep the final (largest) output count

real = sum(sum(t) for t in best.values())
print(f"{len(best):,} responses in {root}")
print(f"Plain sum of the logs: {plain:,} tokens")
print(f"Real usage:            {real:,} tokens" + (f"  (the plain sum is {plain / real:.2f}x too high)" if real else ""))
