"""Did prompt caching save you money on the Claude API? Check it from your own usage logs.

Reads JSON Lines files where each line has a model and an Anthropic usage block, either
  {"model": "claude-sonnet-5-5", "usage": {...}}        (your own logs: log response.model + response.usage)
or Claude Code's local logs ({"message": {"model": ..., "usage": ...}}, priced at API rates).
For every request it compares what you paid with what the same tokens would have cost with no caching
(every cached token billed as plain input). Prints numbers only; sends nothing anywhere.

Usage:  python3 claude_cache_savings.py FILE_OR_FOLDER [...]
        python3 claude_cache_savings.py ~/.claude/projects

Prices are USD per 1 million tokens, from Anthropic's pricing page (checked November 14, 2026).
Standard rates only: Batch API, US-only inference, fast mode and long-prompt prices are not applied.
From https://neverpaytwice.pages.dev/claude-prompt-caching-cost
"""
import json
import pathlib
import sys

PRICES = {
    # model: base input, cache read (hit), output
    "claude-opus-5-5":   {"input": 4.00, "cache_read": 0.20, "output": 20.00},
    "claude-sonnet-5-5": {"input": 2.00, "cache_read": 0.10, "output": 10.00},
    "claude-haiku-5-5":  {"input": 0.10, "cache_read": 0.01, "output": 0.50},   # prompts up to 100,000 tokens
    "claude-fable-5-2":  {"input": 8.00, "cache_read": 0.20, "output": 40.00},
    "claude-fable-5-1":  {"input": 10.00, "cache_read": 0.25, "output": 50.00},
    "claude-opus-5":     {"input": 5.00, "cache_read": 0.50, "output": 25.00},
    "claude-sonnet-5":   {"input": 2.00, "cache_read": 0.20, "output": 10.00},
    "claude-opus-4-8":   {"input": 5.00, "cache_read": 0.50, "output": 25.00},
    "claude-opus-4-7":   {"input": 5.00, "cache_read": 0.50, "output": 25.00},
    "claude-sonnet-4-6": {"input": 3.00, "cache_read": 0.30, "output": 15.00},
    "claude-haiku-4-5":  {"input": 1.00, "cache_read": 0.10, "output": 5.00},
}
WRITE_5M, WRITE_1H = 1.25, 2.0


def break_even_reuses(write_mult, read_mult):
    """Smallest number of cache reads after one write that makes caching cheaper than not caching.

    One write + n reads costs write_mult + n * read_mult (in units of the prompt at input price);
    without caching the same n + 1 requests cost n + 1. Caching wins when n > (write_mult - 1) / (1 - read_mult).
    """
    n = 0
    while write_mult + n * read_mult >= n + 1:
        n += 1
    return n


def costs(model, usage, prices=PRICES):
    """(paid, without caching) in USD for one request, or None if the model has no price."""
    p = prices.get(model)
    if p is None:
        return None
    new_in = usage.get("input_tokens") or 0
    writes = usage.get("cache_creation_input_tokens") or 0
    w1h = (usage.get("cache_creation") or {}).get("ephemeral_1h_input_tokens") or 0
    w5 = max(0, writes - w1h)
    read = usage.get("cache_read_input_tokens") or 0
    out = usage.get("output_tokens") or 0
    paid = (new_in * p["input"] + w5 * p["input"] * WRITE_5M + w1h * p["input"] * WRITE_1H
            + read * p["cache_read"] + out * p["output"]) / 1_000_000
    no_cache = ((new_in + writes + read) * p["input"] + out * p["output"]) / 1_000_000
    return paid, no_cache


def records(paths):
    """Yield (model, usage) once per request. Claude Code logs the same response several times:
    keep one per message id + request id, with the largest output count."""
    seen = {}
    for path in paths:
        path = pathlib.Path(path).expanduser()
        files = sorted(path.rglob("*.jsonl")) if path.is_dir() else [path]
        for f in files:
            for n, line in enumerate(f.open(encoding="utf-8", errors="replace")):
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(o, dict):
                    continue
                m = o.get("message") if isinstance(o.get("message"), dict) else o
                usage, model = m.get("usage"), m.get("model")
                if not isinstance(usage, dict) or not model or model == "<synthetic>":
                    continue
                key = (m.get("id") or "", o.get("requestId") or "")
                if key == ("", ""):
                    key = (str(f), n)
                old = seen.get(key)
                if old is None or (usage.get("output_tokens") or 0) > (old[1].get("output_tokens") or 0):
                    seen[key] = (model, usage)
    return list(seen.values())


def inconsistent(usage):
    """True when the cache-write breakdown can't be right: 1-hour writes above total writes, or a
    5-minute + 1-hour split that doesn't add up to the total. Such lines are listed, not priced."""
    writes = usage.get("cache_creation_input_tokens") or 0
    cc = usage.get("cache_creation")
    if not isinstance(cc, dict):
        return False
    w1h = cc.get("ephemeral_1h_input_tokens") or 0
    if w1h > writes:
        return True
    if "ephemeral_5m_input_tokens" in cc and "ephemeral_1h_input_tokens" in cc:
        return (cc.get("ephemeral_5m_input_tokens") or 0) + w1h != writes
    return False


def summary(recs, prices=PRICES):
    s = {"requests": 0, "unpriced": {}, "inconsistent": 0, "paid": 0.0, "no_cache": 0.0,
         "written": 0, "read": 0, "uncached_input": 0}
    for model, u in recs:
        if inconsistent(u):
            s["inconsistent"] += 1
            continue
        c = costs(model, u, prices)
        if c is None:
            s["unpriced"][model] = s["unpriced"].get(model, 0) + 1
            continue
        s["requests"] += 1
        s["paid"] += c[0]
        s["no_cache"] += c[1]
        s["written"] += u.get("cache_creation_input_tokens") or 0
        s["read"] += u.get("cache_read_input_tokens") or 0
        s["uncached_input"] += u.get("input_tokens") or 0
    s["saved"] = s["no_cache"] - s["paid"]
    return s


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    s = summary(records(sys.argv[1:]))
    if not s["requests"]:
        sys.exit("No priced requests found. Unpriced models: %s. Inconsistent cache-write lines: %d"
                 % (s["unpriced"] or "none", s["inconsistent"]))
    total_in = s["written"] + s["read"] + s["uncached_input"]
    print("Requests:              %d" % s["requests"])
    print("Input tokens:          %d  (%.0f%% read from cache, %.0f%% written to cache)"
          % (total_in, 100 * s["read"] / max(total_in, 1), 100 * s["written"] / max(total_in, 1)))
    print("Reads per written token: %.1f" % (s["read"] / s["written"] if s["written"] else 0))
    print("You paid:              $%.4f" % s["paid"])
    print("Without caching:       $%.4f" % s["no_cache"])
    word = "saved" if s["saved"] >= 0 else "COST YOU EXTRA"
    print("Caching %s:  $%.4f (%.1f%%)" % (word, abs(s["saved"]), 100 * abs(s["saved"]) / max(s["no_cache"], 1e-12)))
    if s["unpriced"]:
        print("Skipped (no price):    %s" % s["unpriced"])
    if s["inconsistent"]:
        print("Skipped (cache-write breakdown doesn't add up): %d request(s); check those log lines" % s["inconsistent"])
