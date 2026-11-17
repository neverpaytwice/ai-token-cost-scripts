"""How much would the Claude Message Batches API save you? Or, if you already batch, what did you pay?

Reads a JSON Lines file of saved Claude API responses (for example message.to_json() from the Python SDK),
or the results file of a Message Batches job (lines with "custom_id" and "result"). Prices every response
at Anthropic's standard rate and at the batch rate (50% of standard on every token, cache reads and writes
included), and groups the totals by model, or by any top-level field you add when saving, such as "job".
Batch results that errored, were canceled or expired are counted but not priced: Anthropic doesn't bill them.
Prints numbers only; sends nothing anywhere.

Usage:  python3 claude_batch_savings.py responses.jsonl [--by FIELD]

Prices are USD per 1 million tokens, from Anthropic's pricing and batch processing pages (checked
November 15, 2026). Fast-mode responses are priced at the standard rate: batches can't use fast mode, so a
batched copy would run at normal speed. Haiku 5.5 prompts over 100,000 tokens and unknown models are listed,
not priced.
From https://neverpaytwice.com/claude-batch-api-cost
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
BATCH = 0.5


def standard_cost(model, u):
    """Standard-rate cost of one response in USD, or None if it can't be priced."""
    p = PRICES.get(model)
    if p is None:
        return None
    prompt = sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    if model == "claude-haiku-5-5" and prompt > 100_000:
        return None
    writes = u.get("cache_creation_input_tokens") or 0
    w1h = (u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens") or 0
    return ((u.get("input_tokens") or 0) * p["input"]
            + max(0, writes - w1h) * p["input"] * WRITE_5M
            + w1h * p["input"] * WRITE_1H
            + (u.get("cache_read_input_tokens") or 0) * p["cache_read"]
            + (u.get("output_tokens") or 0) * p["output"]) / 1_000_000


def read(lines, by=None):
    """Totals per group: [responses, standard $, batch $, already-batched responses]; plus skipped and unbilled."""
    groups, skipped, unbilled = {}, {}, {}
    for line in lines:
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if not isinstance(o, dict):
            continue
        batched = isinstance(o.get("result"), dict)
        msg = o
        if batched:
            r = o["result"]
            if r.get("type") != "succeeded":
                unbilled[r.get("type")] = unbilled.get(r.get("type"), 0) + 1
                continue
            msg = r.get("message") or {}
        if not isinstance(msg.get("usage"), dict):
            continue
        model = msg.get("model")
        c = standard_cost(model, msg["usage"])
        if c is None:
            skipped[model] = skipped.get(model, 0) + 1
            continue
        key = str(o.get(by, "(none)")) if by else model
        g = groups.setdefault(key, [0, 0.0, 0.0, 0])
        g[0] += 1
        g[1] += c
        g[2] += c * BATCH
        g[3] += batched
    return groups, skipped, unbilled


if __name__ == "__main__":
    args = sys.argv[1:]
    by = None
    if "--by" in args:
        i = args.index("--by")
        if i + 1 >= len(args):
            sys.exit(__doc__)
        by = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        sys.exit(__doc__)
    with open(args[0], encoding="utf-8", errors="replace") as f:
        groups, skipped, unbilled = read(f, by)
    if not groups:
        sys.exit("No priced responses found in %s" % args[0])
    print("%-22s %9s %13s %13s %12s" % (by or "model", "responses", "standard", "batch rate", "difference"))
    tot = [0, 0.0, 0.0, 0]
    for key, g in sorted(groups.items(), key=lambda kv: -kv[1][1]):
        print("%-22s %9d %13s %13s %12s" % (key[:22], g[0], "$%.4f" % g[1], "$%.4f" % g[2], "$%.4f" % (g[1] - g[2])))
        tot = [a + b for a, b in zip(tot, g)]
    print("%-22s %9d %13s %13s %12s" % ("total", tot[0], "$%.4f" % tot[1], "$%.4f" % tot[2], "$%.4f" % (tot[1] - tot[2])))
    if tot[3]:
        print("%d of these were already batched: you paid the batch rate for them." % tot[3])
    if unbilled:
        print("Batch results not billed: %s" % ", ".join("%d %s" % (v, k) for k, v in sorted(unbilled.items())))
    if skipped:
        print("Not priced, so not in the totals: %s" % skipped)
