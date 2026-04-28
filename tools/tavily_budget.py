"""
tools/tavily_budget.py — File-backed Tavily daily call budget.

Persists a call counter across process restarts in output/tavily_budget.json.
All three Tavily callers (company_research, job_finder, lead_finder) import
from here so the budget is enforced globally — not per-module or per-process.

Budget file format:
    {"date": "2026-04-28", "calls": 12}

Behaviour:
  - If the date in the file matches today, the stored count is loaded.
  - If the date differs (new day), the counter resets to 0.
  - If the file is missing or unreadable, the counter starts at 0.

Daily cap: 20 calls/day
  Credit math at 20 calls:
    - advanced searches: 2 credits each
    - basic searches:    1 credit each
    Worst case (all advanced): 20 × 2 = 40 credits/day × 30 days = 1,200/month
    Mixed realistic:           ~30 credits/day × 30 days = 900/month — fits free tier.
"""

import json
from datetime import datetime
from pathlib import Path

# Path is resolved relative to this file's location (tools/), then up one level
# to the project root, then into output/. Works regardless of CWD.
_BUDGET_FILE = Path(__file__).resolve().parent.parent / "output" / "tavily_budget.json"

TAVILY_DAILY_LIMIT = 20


def _load() -> dict:
    """
    Load the budget file and return {"date": str, "calls": int}.
    Resets to today/0 if the file is missing, corrupt, or from a previous day.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        data = json.loads(_BUDGET_FILE.read_text(encoding="utf-8"))
        if data.get("date") == today:
            return {"date": today, "calls": int(data.get("calls", 0))}
    except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError):
        pass
    # New day or missing/corrupt file — start fresh
    return {"date": today, "calls": 0}


def _save(data: dict) -> None:
    """Write the budget dict to the budget file."""
    try:
        _BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
        _BUDGET_FILE.write_text(json.dumps(data), encoding="utf-8")
    except OSError as e:
        # Non-fatal — if the write fails we'll just re-read 0 next time.
        print(f"[tavily_budget] Warning: could not write budget file: {e}")


def tavily_ok() -> bool:
    """
    Return True if we still have Tavily budget remaining for today.

    Reads fresh from disk on each call so it's accurate across processes.
    """
    data = _load()
    return data["calls"] < TAVILY_DAILY_LIMIT


def tavily_used() -> None:
    """
    Increment the persistent Tavily call counter by one.

    Reads the current count from disk, increments, writes back. This ensures
    all processes see the same counter even when running in parallel.
    """
    data = _load()
    data["calls"] += 1
    _save(data)


def tavily_status() -> str:
    """Return a human-readable budget status string (for logging)."""
    data = _load()
    remaining = max(0, TAVILY_DAILY_LIMIT - data["calls"])
    return (
        f"Tavily budget: {data['calls']}/{TAVILY_DAILY_LIMIT} calls used today "
        f"({remaining} remaining)"
    )
