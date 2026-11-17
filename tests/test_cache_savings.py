"""Hand-calculated checks for claude_cache_savings.py. Run: python3 tests/test_cache_savings.py

Each expected value is worked out by hand from the prices in the script (USD per million tokens),
not from the script's own output.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import claude_cache_savings as c  # noqa: E402


def close(a, b):
    return abs(a - b) < 1e-12


# 1. Both write types in one request. Sonnet 5.5: input $2, output $10.
#    100 new input, 1,000 five-minute writes, 2,000 one-hour writes, 50 output.
#    paid     = 100*2 + 1000*2*1.25 + 2000*2*2 + 50*10 = 200 + 2500 + 8000 + 500 = 11,200 -> $0.0112
#    no cache = (100 + 3000)*2 + 50*10 = 6,200 + 500 = 6,700 -> $0.0067
u1 = {"input_tokens": 100, "cache_creation_input_tokens": 3000, "cache_read_input_tokens": 0, "output_tokens": 50,
      "cache_creation": {"ephemeral_5m_input_tokens": 1000, "ephemeral_1h_input_tokens": 2000}}
paid, no_cache = c.costs("claude-sonnet-5-5", u1)
assert close(paid, 0.0112) and close(no_cache, 0.0067), (paid, no_cache)

# 2. A cache read followed by an ordinary uncached suffix. Opus 5.5: input $4, cache read $0.20, output $20.
#    20,000 read, 500 new input after the cached prefix, 100 output.
#    paid     = 500*4 + 20000*0.20 + 100*20 = 2000 + 4000 + 2000 = 8,000 -> $0.008
#    no cache = 20500*4 + 100*20 = 82,000 + 2,000 = 84,000 -> $0.084
u2 = {"input_tokens": 500, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 20000, "output_tokens": 100}
paid, no_cache = c.costs("claude-opus-5-5", u2)
assert close(paid, 0.008) and close(no_cache, 0.084), (paid, no_cache)

# 3. Malformed telemetry: one-hour writes above total writes. Must be listed, not priced.
u3 = {"input_tokens": 10, "cache_creation_input_tokens": 100, "output_tokens": 5,
      "cache_creation": {"ephemeral_1h_input_tokens": 300}}
# 4. A 5-minute + 1-hour split that doesn't add up to the total.
u4 = {"input_tokens": 10, "cache_creation_input_tokens": 100, "output_tokens": 5,
      "cache_creation": {"ephemeral_5m_input_tokens": 30, "ephemeral_1h_input_tokens": 30}}
assert c.inconsistent(u3) and c.inconsistent(u4)
assert not c.inconsistent(u1) and not c.inconsistent(u2)
assert not c.inconsistent({"cache_creation_input_tokens": 100})  # no breakdown at all: fine

s = c.summary([("claude-sonnet-5-5", u1), ("claude-opus-5-5", u2), ("claude-sonnet-5-5", u3), ("claude-sonnet-5-5", u4)])
assert s["requests"] == 2 and s["inconsistent"] == 2, s
assert close(s["paid"], 0.0112 + 0.008) and close(s["no_cache"], 0.0067 + 0.084), s

print("all hand-calculated checks passed")
