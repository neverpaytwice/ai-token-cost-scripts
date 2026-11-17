"""Find AI API requests you paid for more than once.

Give it the requests you sent (the JSON body of each call) with the time and the cost you worked out for it.
It groups identical requests and adds up what the repeats cost. Fields that identify the caller rather than
the question (metadata, user, stream_options, service_tier) are ignored, and key order doesn't matter.
From https://neverpaytwice.com/duplicate-ai-api-charges
"""
import hashlib
import json

IGNORE = {"metadata", "user", "stream_options", "service_tier"}


def fingerprint(endpoint, body):
    """Same endpoint + same request body (ignoring caller-only fields) -> same fingerprint."""
    if isinstance(body, dict):
        body = {k: v for k, v in body.items() if k not in IGNORE}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256((endpoint + "\n" + canon).encode()).hexdigest()


def find_repeats(calls):
    """calls: list of dicts with "time", "endpoint", "body" and "cost" (dollars).
    Returns one entry per request that was paid for more than once, most expensive repeats first."""
    groups = {}
    for c in sorted(calls, key=lambda c: c["time"]):
        groups.setdefault(fingerprint(c["endpoint"], c["body"]), []).append(c)
    repeats = []
    for calls_ in groups.values():
        if len(calls_) > 1:
            repeats.append({
                "first": calls_[0]["time"],
                "times_paid": len(calls_),
                "repeat_cost": sum(c["cost"] or 0 for c in calls_[1:]),   # everything after the first purchase
                "seconds_apart": [round(b["time"] - a["time"], 1) for a, b in zip(calls_, calls_[1:])],
            })
    return sorted(repeats, key=lambda r: -r["repeat_cost"])


if __name__ == "__main__":
    ask = {"model": "example-model", "messages": [{"role": "user", "content": "Summarise this contract"}]}
    calls = [
        {"time": 0.0, "endpoint": "/v1/chat/completions", "body": ask, "cost": 0.012},
        {"time": 2.5, "endpoint": "/v1/chat/completions", "body": dict(ask, user="u-42"), "cost": 0.012},  # double-click
        {"time": 900.0, "endpoint": "/v1/chat/completions", "body": ask, "cost": 0.011},                   # asked again later
        {"time": 30.0, "endpoint": "/v1/chat/completions", "body": dict(ask, messages=[{"role": "user", "content": "Different question"}]), "cost": 0.004},
    ]
    for r in find_repeats(calls):
        print(r)   # {'first': 0.0, 'times_paid': 3, 'repeat_cost': 0.023, 'seconds_apart': [2.5, 897.5]}
