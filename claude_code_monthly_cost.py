"""What would your Claude Code usage cost each month at API rates? Compare it with the plan price.

Reads Claude Code's local logs (~/.claude/projects). Claude Code writes each response several times, so this
keeps one record per response (message id + request id, largest output count), prices it at Anthropic's
standard API rates, and adds it up per calendar month (UTC). Prints numbers only; sends nothing anywhere.

Usage:  python3 claude_code_monthly_cost.py [path-to-projects-folder]

Prices are USD per 1 million tokens, from Anthropic's pricing page (checked November 14, 2026).
Standard rates only: Batch API, US-only inference, fast mode and long-prompt prices are not applied.
Plan prices are from claude.com/pricing (checked November 14, 2026); plans have usage limits that
Anthropic does not publish in tokens, so a plan that looks cheaper can still run out.
From https://neverpaytwice.com/claude-code-subscription-vs-api
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
PLANS = [("Pro", 20), ("Max", 100), ("Ultra", 200)]   # USD per month, billed monthly


def cost(model, u, prices=PRICES):
    """Dollar cost of one response at API rates, or None if the model has no price."""
    p = prices.get(model)
    if p is None:
        return None
    writes = u.get("cache_creation_input_tokens") or 0
    w1h = (u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens") or 0
    return ((u.get("input_tokens") or 0) * p["input"]
            + max(0, writes - w1h) * p["input"] * WRITE_5M
            + w1h * p["input"] * WRITE_1H
            + (u.get("cache_read_input_tokens") or 0) * p["cache_read"]
            + (u.get("output_tokens") or 0) * p["output"]) / 1_000_000


def responses(root):
    """One (month, model, usage) per response, from Claude Code's logs."""
    best = {}
    for f in sorted(pathlib.Path(root).expanduser().rglob("*.jsonl")):
        for n, line in enumerate(f.open(encoding="utf-8", errors="replace")):
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if not isinstance(o, dict):
                continue
            m = o.get("message")
            if o.get("type") != "assistant" or not isinstance(m, dict) or not isinstance(m.get("usage"), dict):
                continue
            if m.get("model") == "<synthetic>" or o.get("isApiErrorMessage"):
                continue
            key = (m.get("id") or "", o.get("requestId") or "")
            if key == ("", ""):
                key = (str(f), n)
            old = best.get(key)
            if old is None or (m["usage"].get("output_tokens") or 0) > (old[2].get("output_tokens") or 0):
                best[key] = ((o.get("timestamp") or "")[:7] or "unknown", m.get("model"), m["usage"])
    return list(best.values())


def monthly(recs, prices=PRICES):
    """{month: dollars}, plus {model: responses skipped because they have no price}."""
    months, unpriced = {}, {}
    for month, model, u in recs:
        c = cost(model, u, prices)
        if c is None:
            unpriced[model] = unpriced.get(model, 0) + 1
            continue
        months[month] = months.get(month, 0.0) + c
    return months, unpriced


def unpriced_months(recs, prices=PRICES):
    """{month: responses in that month left out because their model has no price}. Those months read low."""
    out = {}
    for month, model, u in recs:
        if cost(model, u, prices) is None:
            out[month] = out.get(month, 0) + 1
    return out


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else pathlib.Path.home() / ".claude" / "projects"
    recs = responses(root)
    months, unpriced = monthly(recs)
    gaps = unpriced_months(recs)
    if not months:
        sys.exit("No priced Claude Code responses found in %s" % root)
    print("%-9s %13s" % ("Month", "At API rates") + "".join("%22s" % ("%s $%d/mo" % p) for p in PLANS))
    for month in sorted(months):
        usd = months[month]
        cols = "".join("%22s" % ("plan cheaper by $%.0f" % (usd - price) if usd > price else "API cheaper by $%.0f" % (price - usd))
                       for _, price in PLANS)
        print("%-9s %13s" % (month, "$%.2f" % usd + ("*" if month in gaps else "")) + cols)
    if unpriced:
        print("Skipped (no price): %s" % unpriced)
        print("* Incomplete month: %s. Some responses there use a model with no price in PRICES, so the total reads low."
              % ", ".join("%s (%d left out)" % (m, n) for m, n in sorted(gaps.items())))
        print("  Add the model's price to PRICES and run again.")
    print("A month that is still running is only partly counted.")
