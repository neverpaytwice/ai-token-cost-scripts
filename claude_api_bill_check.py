"""Why is my Claude API bill so high? Find out where the money goes in your own responses.

Reads a JSON Lines file where each line is a saved Messages API response (for example message.to_json()
from the Python SDK) or any object with "model" and "usage". Prices each response at Anthropic's standard
API rates and shows what the money went on: new input, cache writes, cache reads, output and the thinking
inside it. Also lists requests that sent a lot of new input with no cache reads (caching candidates) and
requests whose price this script can't fully know (fast mode on some models, long Haiku 5.5 prompts).
Prints numbers only; sends nothing anywhere.

Usage:  python3 claude_api_bill_check.py responses.jsonl

Prices are USD per 1 million tokens, from Anthropic's pricing page (checked November 15, 2026).
Batch API, US-only inference and long-prompt prices are not applied. Fast mode is priced only for
Claude Opus 5.5 ($8 / $40, twice the standard rate); other fast-mode responses are listed, not priced.
From https://neverpaytwice.pages.dev/claude-api-bill-too-high
"""
import json
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
FAST_MULTIPLIER = {"claude-opus-5-5": 2.0}   # only fast-mode rates we have checked
NO_CACHE_FLAG = 10_000                        # new input tokens with zero cache reads worth a look


def n(u, key):
    return u.get(key) or 0


def split(model, u):
    """Dollar cost of one response, split into parts, or None if it can't be priced."""
    p = PRICES.get(model)
    if p is None:
        return None
    mult = 1.0
    if u.get("speed") == "fast":
        if model not in FAST_MULTIPLIER:
            return None
        mult = FAST_MULTIPLIER[model]
    writes = n(u, "cache_creation_input_tokens")
    w1h = n(u.get("cache_creation") or {}, "ephemeral_1h_input_tokens")
    thinking = n(u.get("output_tokens_details") or {}, "thinking_tokens")
    out = n(u, "output_tokens")
    m = mult / 1_000_000
    return {
        "new input": n(u, "input_tokens") * p["input"] * m,
        "cache writes (5 min)": max(0, writes - w1h) * p["input"] * WRITE_5M * m,
        "cache writes (1 hour)": w1h * p["input"] * WRITE_1H * m,
        "cache reads": n(u, "cache_read_input_tokens") * p["cache_read"] * m,
        "output (not thinking)": max(0, out - thinking) * p["output"] * m,
        "thinking (billed as output)": min(thinking, out) * p["output"] * m,
    }


def check(lines):
    totals, unpriced, no_cache, models = {}, [], [], {}
    count = in_tok = read_tok = 0
    for i, line in enumerate(lines, 1):
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if not isinstance(o, dict) or not isinstance(o.get("usage"), dict):
            continue
        model, u = o.get("model"), o["usage"]
        prompt = n(u, "input_tokens") + n(u, "cache_creation_input_tokens") + n(u, "cache_read_input_tokens")
        if model == "claude-haiku-5-5" and prompt > 100_000:
            unpriced.append((i, model, "Haiku 5.5 prompt over 100,000 tokens"))
            continue
        parts = split(model, u)
        if parts is None:
            why = "fast mode" if u.get("speed") == "fast" else "no price for this model"
            unpriced.append((i, model, why))
            continue
        count += 1
        in_tok += prompt
        read_tok += n(u, "cache_read_input_tokens")
        for k, v in parts.items():
            totals[k] = totals.get(k, 0.0) + v
        models[model] = models.get(model, 0.0) + sum(parts.values())
        if n(u, "input_tokens") >= NO_CACHE_FLAG and not n(u, "cache_read_input_tokens"):
            no_cache.append((i, model, n(u, "input_tokens")))
    return count, totals, models, unpriced, no_cache, in_tok, read_tok


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
        count, totals, models, unpriced, no_cache, in_tok, read_tok = check(f)
    if not count:
        sys.exit("No priced responses found in %s" % sys.argv[1])
    total = sum(totals.values())
    print("%d responses, $%.4f at standard API rates\n" % (count, total))
    print("Where the money went:")
    for k, v in sorted(totals.items(), key=lambda kv: -kv[1]):
        print("  %-28s $%10.4f  %5.1f%%" % (k, v, 100 * v / total if total else 0))
    print("\nBy model:")
    for k, v in sorted(models.items(), key=lambda kv: -kv[1]):
        print("  %-28s $%10.4f" % (k, v))
    print("\nPrompt tokens read from cache: %.1f%%" % (100 * read_tok / in_tok if in_tok else 0))
    if no_cache:
        print("%d responses sent %s+ new input tokens with no cache reads (lines: %s)"
              % (len(no_cache), format(NO_CACHE_FLAG, ","), ", ".join(str(x[0]) for x in no_cache[:10])
                 + (" ..." if len(no_cache) > 10 else "")))
    if unpriced:
        print("Not priced, so not in the total: %d (%s)"
              % (len(unpriced), "; ".join("line %d %s: %s" % x for x in unpriced[:5])
                 + (" ..." if len(unpriced) > 5 else "")))
