"""What one Anthropic (Claude) API request cost, from the usage block that comes back with it.

Prices are USD per 1 million tokens, from Anthropic's pricing page (checked November 14, 2026).
Cache writes are priced from the input price: 1.25x for the 5-minute cache, 2x for the 1-hour cache.
Cache reads have their own price per model. Claude Haiku 5.5 has a higher price for a request whose
prompt (new input + cache writes + cache reads) is over 100,000 tokens; that is applied below.
Check the pricing page and update PRICES when it changes.
From https://neverpaytwice.com/anthropic-api-cost-per-request
"""

PRICES = {
    # model: base input, cache read (hit), output
    "claude-opus-5-5":   {"input": 4.00, "cache_read": 0.20, "output": 20.00},
    "claude-sonnet-5-5": {"input": 2.00, "cache_read": 0.10, "output": 10.00},
    "claude-haiku-5-5":  {"input": 0.10, "cache_read": 0.01, "output": 0.50},   # prompts up to 100,000 tokens
    "claude-fable-5-2":  {"input": 8.00, "cache_read": 0.20, "output": 40.00},
    "claude-opus-4-8":   {"input": 5.00, "cache_read": 0.50, "output": 25.00},
    "claude-sonnet-4-6": {"input": 3.00, "cache_read": 0.30, "output": 15.00},
    "claude-haiku-4-5":  {"input": 1.00, "cache_read": 0.10, "output": 5.00},
}
# Requests whose whole prompt is over 100,000 tokens are priced here instead.
LONG_PROMPT_PRICES = {
    "claude-haiku-5-5":  {"input": 0.50, "cache_read": 0.05, "output": 2.50},   # prompts over 100,000 tokens
}
LONG_PROMPT_TOKENS = 100_000
WRITE_5M, WRITE_1H = 1.25, 2.0


def split_usage(usage):
    """Return (new input, 5-minute cache writes, 1-hour cache writes, cache reads, output) token counts.

    Anthropic's input_tokens already EXCLUDES cached tokens: the total input of a request is
    input_tokens + cache_creation_input_tokens + cache_read_input_tokens.
    output_tokens already INCLUDES thinking tokens.
    """
    writes = usage.get("cache_creation_input_tokens") or 0
    write_1h = (usage.get("cache_creation") or {}).get("ephemeral_1h_input_tokens") or 0
    return (usage.get("input_tokens") or 0,
            max(0, writes - write_1h),          # the default cache lasts 5 minutes
            write_1h,
            usage.get("cache_read_input_tokens") or 0,
            usage.get("output_tokens") or 0)


def request_cost(model, usage, prices=PRICES, long_prices=LONG_PROMPT_PRICES):
    """Dollar cost of one request, or None if the model has no price in `prices`."""
    p = prices.get(model)
    if p is None:
        return None
    new_in, w5, w1h, read, out = split_usage(usage)
    if new_in + w5 + w1h + read > LONG_PROMPT_TOKENS and model in long_prices:
        p = long_prices[model]
    return (new_in * p["input"]
            + w5 * p["input"] * WRITE_5M
            + w1h * p["input"] * WRITE_1H
            + read * p["cache_read"]
            + out * p["output"]) / 1_000_000


if __name__ == "__main__":
    usage = {"input_tokens": 1200, "cache_creation_input_tokens": 2000,
             "cache_creation": {"ephemeral_5m_input_tokens": 2000, "ephemeral_1h_input_tokens": 0},
             "cache_read_input_tokens": 10000, "output_tokens": 400,
             "output_tokens_details": {"thinking_tokens": 150}}
    print(round(request_cost("claude-sonnet-5-5", usage), 6))   # 0.0124
