# AI token cost scripts

Small, dependency-free Python 3 scripts for checking what your AI usage really cost.
Each one reads local files or a response's `usage` block, prints numbers, and sends nothing anywhere.

| Script | What it answers | Guide |
|---|---|---|
| [`count_claude_code_tokens.py`](count_claude_code_tokens.py) | How many tokens has Claude Code really used? Its logs repeat each response several times, so a plain sum over-counts. | [Why Claude Code token counts are wrong](https://neverpaytwice.pages.dev/claude-code-token-count) |
| [`claude_cache_savings.py`](claude_cache_savings.py) | Did prompt caching save money, or cost extra? Compares what you paid with the same tokens billed with no caching. | [Claude prompt caching break-even math](https://neverpaytwice.pages.dev/claude-prompt-caching-cost) |
| [`claude_code_monthly_cost.py`](claude_code_monthly_cost.py) | Is a Claude plan (Pro, Max, Ultra) or the API cheaper for your Claude Code use? Prices each month of your logs at API rates and compares it with each plan. | [Claude Code: subscription or API?](https://neverpaytwice.pages.dev/claude-code-subscription-vs-api) |
| [`claude_api_bill_check.py`](claude_api_bill_check.py) | Why is your Claude API bill so high? Splits the cost of saved API responses into new input, cache writes, cache reads, output and thinking, and lists requests that skipped the cache. | [Why is my Claude API bill so high?](https://neverpaytwice.pages.dev/claude-api-bill-too-high) |
| [`anthropic_request_cost.py`](anthropic_request_cost.py) | What did one Claude API request cost, from its `usage` block (input, 5-minute and 1-hour cache writes, cache reads, output)? | [What each Claude API request costs](https://neverpaytwice.pages.dev/anthropic-api-cost-per-request) |
| [`openai_request_cost.py`](openai_request_cost.py) | What did one OpenAI request cost (Chat Completions or Responses API, cached input split out)? Fill in your prices. | [What each OpenAI API request costs](https://neverpaytwice.pages.dev/openai-api-cost-per-request) |
| [`find_repeat_requests.py`](find_repeat_requests.py) | Which requests did you pay for more than once (retries, double-clicks, re-run pipelines)? | [How to spot duplicate AI API charges](https://neverpaytwice.pages.dev/duplicate-ai-api-charges) |

## Quick start

```bash
python3 count_claude_code_tokens.py              # reads ~/.claude/projects
python3 claude_cache_savings.py ~/.claude/projects
python3 claude_code_monthly_cost.py             # API-rate cost per month vs plan prices
python3 claude_api_bill_check.py responses.jsonl  # where your API bill went (saved responses, one JSON per line)
```

Works on macOS, Linux and Windows. No packages to install.

Example output on the made-up sample in [`sample/`](sample) (30 responses over two months, each logged 2 to 4 times as Claude Code does):

```
$ python3 count_claude_code_tokens.py ./sample
30 responses in sample
Plain sum of the logs: 5,333,367 tokens
Real usage:            1,794,898 tokens  (the plain sum is 2.97x too high)

$ python3 claude_cache_savings.py ./sample
Requests:              30
Input tokens:          1773074  (97% read from cache, 3% written to cache)
Reads per written token: 32.4
You paid:              $0.5240
Without caching:       $3.7644
Caching saved:  $3.2404 (86.1%)
```

Claude prices in the scripts are Anthropic's standard API rates, checked November 14, 2026. Batch, fast mode,
regional and long-prompt prices are not applied. Claude Code subscription plans are not billed per token; the
dollar figures show what the same usage would cost at API rates.

## Prefer not to run scripts?

- **[Free in-browser Claude Code counter](https://neverpaytwice.pages.dev/count)**: drop in your logs; files are read in the browser and never uploaded.
- **[NeverPayTwice](https://neverpaytwice.pages.dev/)**: a small app ($9 one-time) that does all of the above continuously across AI tools,
  flags repeat charges, and keeps a receipt for each AI purchase. Runs on your own computer.

## License

MIT. Issues and corrections welcome, especially when a provider changes its prices.
