"""
client_hunt/lead_finder.py — Buy-signal lead discovery for AI enablement / L&D consulting.

Uses Exa + Tavily to surface companies showing strong intent to hire or invest in
L&D / AI enablement — Jon's target buyers.

Buy signals tracked:
  - AI initiative announcements ("AI enablement", "workforce AI")
  - L&D leadership hiring (Director/VP/CLO roles)
  - Series B+ funding (budget unlocked)
  - LMS migration / digital transformation announcements
  - AI readiness / upskilling initiatives
"""

import os
import re
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

import sys
from pathlib import Path
# Allow importing from tools/ when running from project root or sub-directories
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.tavily_budget import tavily_ok, tavily_used


SIGNAL_QUERIES = [
    ("ai_initiative", '"AI training program" OR "AI enablement" OR "workforce AI" company announcement'),
    ("hiring_ld",     '"director of learning" OR "VP learning" OR "chief learning officer" job opening'),
    ("funding",       '"Series B" OR "Series C" technology company 2025 2026 site:businesswire.com OR site:techcrunch.com'),
    ("lms_migration", '"LMS migration" OR "learning platform" OR "digital transformation training"'),
    ("ai_initiative", '"upskilling" OR "reskilling" OR "AI readiness" workforce 2026'),
]

TAVILY_QUERIES = [
    "company AI training workforce upskilling program 2026",
    "enterprise learning development digital transformation announcement",
    "AI enablement corporate training initiative 2026",
]

SIGNAL_SCORES = {
    "funding":       9,
    "ai_initiative": 8,
    "hiring_ld":     7,
    "lms_migration": 6,
}


class LeadFinder:
    """
    Searches Exa + Tavily for companies showing buy signals for AI enablement / L&D.
    Returns deduplicated, scored lead dicts.
    """

    def __init__(self):
        from exa_py import Exa
        from tavily import TavilyClient
        self.exa    = Exa(api_key=os.getenv("EXA_API_KEY"))
        self.tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

    def search(self) -> list[dict]:
        """
        Run all signal queries and return deduplicated, scored leads.
        """
        leads = []

        # Exa signal queries (last 30 days for hiring/AI; 90 days for funding)
        for signal_type, query in SIGNAL_QUERIES:
            days = 90 if signal_type == "funding" else 30
            start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
            try:
                res = self.exa.search_and_contents(
                    query,
                    num_results=8,
                    start_published_date=start_date,
                    highlights={"max_characters": 1000},
                )
                for r in res.results:
                    url = r.url or ""
                    if not url:
                        continue
                    desc = " ".join(r.highlights) if r.highlights else (r.title or "")
                    leads.append({
                        "company_name": self._infer_company(url, r.title or ""),
                        "domain":       _extract_domain(url),
                        "signal_type":  signal_type,
                        "signal_text":  desc[:400],
                        "signal_url":   url,
                        "signal_date":  getattr(r, "published_date", "") or "",
                        "buy_signal_score": 0,   # filled by _score_lead
                        "source":       "exa",
                    })
            except Exception as e:
                print(f"[lead_finder/exa] {signal_type}: {e}")
            time.sleep(0.2)

        # Tavily queries (last 90 days) — gated by shared daily budget
        for query in TAVILY_QUERIES:
            if not tavily_ok():
                print(f"[lead_finder/tavily] Daily budget exhausted — skipping remaining Tavily queries")
                break
            try:
                tavily_used()
                res = self.tavily.search(
                    query=query,
                    search_depth="advanced",
                    max_results=8,
                    include_answer=False,
                    days=90,
                )
                for r in res.get("results", []):
                    url = r.get("url", "")
                    if not url:
                        continue
                    # Infer signal type from content
                    content = (r.get("content", "") + " " + r.get("title", "")).lower()
                    signal_type = _infer_signal_type(content)
                    leads.append({
                        "company_name": self._infer_company(url, r.get("title", "")),
                        "domain":       _extract_domain(url),
                        "signal_type":  signal_type,
                        "signal_text":  r.get("content", "")[:400],
                        "signal_url":   url,
                        "signal_date":  r.get("published_date", ""),
                        "buy_signal_score": 0,
                        "source":       "tavily",
                    })
            except Exception as e:
                print(f"[lead_finder/tavily] {e}")
            time.sleep(0.2)

        # Score, deduplicate, sort
        for lead in leads:
            lead["buy_signal_score"] = self._score_lead(lead)

        leads = self._deduplicate(leads)
        leads.sort(key=lambda l: -l["buy_signal_score"])

        print(f"[lead_finder] {len(leads)} unique leads found")
        return leads

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _score_lead(self, lead: dict) -> int:
        """Score 1-10 based on signal type."""
        return SIGNAL_SCORES.get(lead.get("signal_type", ""), 5)

    def _deduplicate(self, leads: list) -> list:
        """Deduplicate by domain, keeping highest-scored entry per domain."""
        by_domain: dict[str, dict] = {}
        for lead in leads:
            domain = lead.get("domain", "")
            if not domain or domain == "unknown":
                continue
            existing = by_domain.get(domain)
            if not existing or lead["buy_signal_score"] > existing["buy_signal_score"]:
                by_domain[domain] = lead
        return list(by_domain.values())

    def _infer_company(self, url: str, title: str) -> str:
        """Infer company name from URL or title. Mirrors tools/job_finder.py logic."""
        def _slug_to_name(slug: str) -> str:
            return " ".join(w.capitalize() for w in re.split(r"[-_]+", slug) if w)

        if not url:
            if title:
                m = re.search(r"\bat\s+([A-Za-z][^\s,|@]{1,40})$", title.strip(), re.IGNORECASE)
                if m:
                    return m.group(1).strip().rstrip(".,")
            return "Unknown Company"

        parsed     = urlparse(url)
        host       = (parsed.hostname or "").lower()
        host_parts = host.split(".")
        path_parts = [p for p in parsed.path.split("/") if p]

        _SKIP = {"jobs", "job", "careers", "career", "apply", "positions", "j", "o",
                 "news", "press", "blog", "about"}

        # Title "at Company" pattern
        if title:
            for pat in (r"\bat\s+([A-Za-z][^\s,|()\[\]]{1,40})$",
                        r"@\s*([A-Za-z][^\s,|()\[\]]{1,40})$"):
                m = re.search(pat, title.strip(), re.IGNORECASE)
                if m:
                    cand = m.group(1).strip().rstrip(".,")
                    if len(cand) > 1:
                        return cand

        # Subdomain pattern (careers.company.com)
        CAREER_SUBS = {"careers", "jobs", "job", "hiring", "work", "join", "talent", "press", "newsroom"}
        if len(host_parts) >= 3 and host_parts[0] in CAREER_SUBS and host_parts[1] not in {"co", "com", "net", "org"}:
            return _slug_to_name(host_parts[1])

        # www.company.com
        base = host_parts[0] if host_parts[0] != "www" else (host_parts[1] if len(host_parts) > 1 else "")
        if base:
            return _slug_to_name(base)

        return "Unknown Company"


# ------------------------------------------------------------------
# Module helpers
# ------------------------------------------------------------------

def _extract_domain(url: str) -> str:
    """Extract registrable domain from URL."""
    try:
        host = urlparse(url).hostname or ""
        parts = host.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return host
    except Exception:
        return "unknown"


def _infer_signal_type(text: str) -> str:
    """Infer signal type from content text."""
    if any(w in text for w in ("series b", "series c", "funding", "raised", "investment")):
        return "funding"
    if any(w in text for w in ("director of learning", "vp learning", "chief learning", "clo", "l&d manager")):
        return "hiring_ld"
    if any(w in text for w in ("lms", "learning platform", "lms migration")):
        return "lms_migration"
    return "ai_initiative"
