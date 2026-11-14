"""Work out what one OpenAI API request cost, from the `usage` block in its response.

Works with Chat Completions usage (prompt_tokens / completion_tokens) and Responses API usage
(input_tokens / output_tokens). Cached input is split out because it is billed at a lower rate.
Reasoning tokens are already included in the output count, so they are not added again.
Fill in PRICES from OpenAI's pricing page for the models you use (US dollars per 1 million tokens).
From https://neverpaytwice.pages.dev/openai-api-cost-per-request
"""

PRICES = {
    # "model-name": {"input": 0.00, "cached_input": 0.00, "output": 0.00},
}


def split_usage(usage):
    """Return (new input, cached input, output) token counts from a response's usage block."""
    if "prompt_tokens" in usage or "completion_tokens" in usage:          # Chat Completions
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        return (usage.get("prompt_tokens") or 0) - cached, cached, usage.get("completion_tokens") or 0
    cached = (usage.get("input_tokens_details") or {}).get("cached_tokens") or 0   # Responses API
    return (usage.get("input_tokens") or 0) - cached, cached, usage.get("output_tokens") or 0


def request_cost(model, usage, prices=PRICES):
    """Dollar cost of one request, or None if the model has no price in `prices`."""
    p = prices.get(model)
    if p is None:
        return None
    new_in, cached_in, out = split_usage(usage)
    return (new_in * p["input"] + cached_in * p["cached_input"] + out * p["output"]) / 1_000_000


if __name__ == "__main__":
    # Example with made-up prices; replace them with the real ones for your model.
    example_prices = {"example-model": {"input": 2.00, "cached_input": 0.50, "output": 8.00}}
    usage = {"prompt_tokens": 1200, "completion_tokens": 300, "prompt_tokens_details": {"cached_tokens": 1000}}
    print(split_usage(usage))                                        # (200, 1000, 300)
    print(f"${request_cost('example-model', usage, example_prices):.6f}")  # $0.003300
