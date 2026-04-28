"""
tools/job_finder.py — Job discovery engine.

Strategy:
  1. Search directly for company career page URLs (not aggregators)
     — jobs posted on the company's own site go straight to the ATS form,
       bypassing aggregator friction and giving us better apply rates
  2. Sort results by recency — last 24 hours is top priority, last 7 days secondary
  3. Filter out aggregator domains (LinkedIn, Indeed, Glassdoor, etc.)
     unless no direct URL is found for that company

Exa is ideal here: neural search understands "AI Enablement Lead job opening"
and surfaces actual career pages rather than SEO-stuffed aggregator listings.
Tavily provides freshness signals via its date-aware search.
"""

import os
import re
import time
import urllib.request
import json
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

from dotenv import load_dotenv
from exa_py import Exa
from tavily import TavilyClient

load_dotenv()

from config import TARGET_ROLES, JOB_PREFERENCES

# JobRight.ai session cookie — stored in .env as JOBRIGHT_SESSION_ID
JOBRIGHT_SESSION = os.environ.get("JOBRIGHT_SESSION_ID", "3e9e3d0100d24b4c8f85ee6b965a9c1c")

SEARCH_ROLES     = TARGET_ROLES
SEARCH_LOCATIONS = JOB_PREFERENCES["locations"]

# Domains we actively avoid — jobs there go through their own apply flow,
# not the company's ATS. Only kept as fallback when no direct URL found.
AGGREGATOR_DOMAINS = {
    "linkedin.com", "indeed.com", "glassdoor.com", "monster.com",
    "ziprecruiter.com", "simplyhired.com", "careerbuilder.com",
    "dice.com", "hired.com", "wellfound.com", "angel.co",
    "builtin.com", "themuse.com", "flexjobs.com", "remote.co",
    "naukri.com", "timesjobs.com", "shine.com",
}

# Domains that ARE direct ATS pages (we want these)
ATS_DOMAINS = {
    "lever.co", "greenhouse.io", "ashbyhq.com", "myworkdayjobs.com",
    "smartrecruiters.com", "bamboohr.com", "icims.com", "taleo.net",
    "jobvite.com", "breezy.hr", "recruitee.com", "workable.com",
}


def _is_aggregator(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return any(agg in host for agg in AGGREGATOR_DOMAINS)


def _is_direct(url: str) -> bool:
    """True if URL points to a company career page or known ATS."""
    host = urlparse(url).hostname or ""
    if any(ats in host for ats in ATS_DOMAINS):
        return True
    path = urlparse(url).path.lower()
    if any(kw in path for kw in ("/careers/", "/jobs/", "/job/", "/openings/", "/positions/")):
        return True
    return False


def _parse_date(date_str: str) -> datetime | None:
    """Try to parse a date string into a UTC datetime."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _age_hours(posted_date: str) -> float:
    """Return hours since posting. Returns 999 if unknown."""
    dt = _parse_date(posted_date)
    if not dt:
        return 999
    now = datetime.now(timezone.utc)
    delta = now - dt
    return delta.total_seconds() / 3600


def _freshness_score(posted_date: str) -> int:
    """
    Priority score based on recency.
      0-24h  → 100  (highest priority)
      24-72h → 70
      3-7d   → 40
      >7d    → 10
    """
    hours = _age_hours(posted_date)
    if hours <= 24:
        return 100
    if hours <= 72:
        return 70
    if hours <= 168:
        return 40
    return 10


class JobFinder:

    def __init__(self):
        self.tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        self.exa    = Exa(api_key=os.getenv("EXA_API_KEY"))
        self.jobright_session = JOBRIGHT_SESSION

    def search(self, freshness_days: int = 7) -> list[dict]:
        """
        Find job postings.

        Priority order:
          1. Direct company career pages found within last 24 hours
          2. Direct career pages found within last 7 days
          3. ATS-hosted pages (Lever, Greenhouse, etc.) — still direct
          4. Aggregator fallback (only if no direct found for that query)

        Args:
            freshness_days: max age of results in days (default 7)

        Returns:
            Deduplicated list of job dicts, sorted by freshness score descending.
        """
        jobs = []
        cutoff_hours = freshness_days * 24

        # Search 0: JobRight.ai — AI-matched recommendations, highest quality signal
        jobright_jobs = self._search_jobright()
        jobs += jobright_jobs
        print(f"[job_finder/jobright] {len(jobright_jobs)} jobs")

        for role in SEARCH_ROLES:
            for loc in SEARCH_LOCATIONS:
                # Search 1: direct career pages via Exa (neural, recency-biased)
                exa_jobs = self._search_exa_direct(role, loc, freshness_days)
                jobs += exa_jobs

                # Search 2: Tavily with site: operators to surface company careers
                tavily_jobs = self._search_tavily_direct(role, loc)
                jobs += tavily_jobs

                time.sleep(0.2)

        # Deduplicate by URL
        jobs = self._deduplicate(jobs)

        # Filter by freshness
        jobs = [j for j in jobs if _age_hours(j.get("posted_date", "")) <= cutoff_hours
                or j.get("posted_date") == ""]

        # Sort: direct/ATS first, then by freshness score descending
        jobs.sort(key=lambda j: (
            0 if _is_direct(j.get("url", "")) else 1,   # direct pages first
            -_freshness_score(j.get("posted_date", "")),  # freshest first
        ))

        # Log breakdown
        today_count = sum(1 for j in jobs if _age_hours(j.get("posted_date", "")) <= 24)
        week_count  = len(jobs) - today_count
        direct      = sum(1 for j in jobs if _is_direct(j.get("url", "")))
        print(f"[job_finder] {len(jobs)} jobs | {today_count} from last 24h | "
              f"{week_count} older | {direct} direct URLs")

        return jobs

    # ------------------------------------------------------------------
    # Exa search — direct company pages
    # ------------------------------------------------------------------

    def _search_jobright(self, limit: int = 50) -> list[dict]:
        """
        Pull AI-matched job recommendations from JobRight.ai.

        JobRight uses our profile to score matches — results are pre-ranked
        by fit. We get displayScore (0-100) as the match signal.
        Uses the SESSION_ID cookie from .env / JOBRIGHT_SESSION_ID.
        """
        if not self.jobright_session:
            return []

        url = (
            f"https://jobright.ai/swan/recommend/list/jobs"
            f"?refresh=true&sortCondition=0&position=0&limit={limit}"
        )
        headers = {
            "Cookie": f"SESSION_ID={self.jobright_session}",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "Referer": "https://jobright.ai/jobs",
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())

            if not data.get("success"):
                print(f"[job_finder/jobright] API error: {data.get('errorMsg')}")
                return []

            raw_jobs = data.get("result", {}).get("jobList", [])
            jobs = []
            for item in raw_jobs:
                jr = item.get("jobResult", {})
                cr = item.get("companyResult", {})
                match_score = item.get("displayScore", 0)

                job_id  = jr.get("jobId", "")
                title   = jr.get("jobTitle", "")
                company = cr.get("name", jr.get("companyName", ""))
                loc_str = jr.get("jobLocation", "")
                remote  = jr.get("isRemote", False)
                summary = jr.get("jobSummary", "")
                posted  = jr.get("publishTime", "")
                apply_url = jr.get("url", f"https://jobright.ai/jobs/{job_id}")

                # Only remote jobs
                if not remote and "remote" not in (loc_str + title).lower():
                    continue

                jobs.append({
                    "title":        title,
                    "url":          apply_url,
                    "company":      company,
                    "description":  summary[:500],
                    "posted_date":  posted,
                    "source":       "jobright",
                    "match_score":  round(match_score),
                })

            return jobs

        except Exception as e:
            print(f"[job_finder/jobright] Error: {e}")
            return []

    def _search_exa_direct(self, role: str, loc: str,
                           freshness_days: int = 7) -> list[dict]:
        """
        Use Exa neural search to find job postings on company career pages.
        Exclude aggregators via site exclusions.
        """
        query = (
            f'"{role}" job opening career site:lever.co OR site:greenhouse.io OR '
            f'site:ashbyhq.com OR site:myworkdayjobs.com OR site:bamboohr.com OR '
            f'site:smartrecruiters.com OR site:breezy.hr OR site:recruitee.com '
            f'{loc if loc != "Remote" else "remote"}'
        )

        # Also run a broader query for companies' own /careers/ pages
        company_query = (
            f'"{role}" job opening remote {loc} site:*/careers/* OR site:*/jobs/*'
        )

        results = []
        for q in (query, company_query):
            try:
                # Use date filter — only results from last freshness_days days
                start_date = (datetime.now(timezone.utc)
                              - timedelta(days=freshness_days)).strftime("%Y-%m-%d")

                res = self.exa.search_and_contents(
                    q,
                    num_results=8,
                    start_published_date=start_date,
                    highlights={"max_characters": 1000},
                )
                for r in res.results:
                    url = r.url or ""
                    if _is_aggregator(url):
                        continue
                    desc = " ".join(r.highlights) if r.highlights else ""
                    results.append({
                        "title":       r.title or role,
                        "url":         url,
                        "company":     self._infer_company(url, r.title or ""),
                        "description": desc[:500],
                        "posted_date": getattr(r, "published_date", "") or "",
                        "source":      "exa_direct",
                    })
            except Exception as e:
                print(f"[job_finder/exa] {e}")

        return results

    # ------------------------------------------------------------------
    # Tavily search — recency-aware
    # ------------------------------------------------------------------

    def _search_tavily_direct(self, role: str, loc: str) -> list[dict]:
        """
        Use Tavily with time-filtered search to find fresh postings.
        Focus on last 7 days. Filter out aggregators post-search.
        """
        query = f'"{role}" job opening {loc} -site:linkedin.com -site:indeed.com -site:glassdoor.com'

        try:
            res = self.tavily.search(
                query=query,
                search_depth="advanced",
                max_results=8,
                include_answer=False,
                days=7,          # Tavily freshness filter — last 7 days only
            )
            jobs = []
            for r in res.get("results", []):
                url = r.get("url", "")
                if _is_aggregator(url):
                    continue
                jobs.append({
                    "title":       r.get("title", role),
                    "url":         url,
                    "company":     self._infer_company(url, r.get("title", "")),
                    "description": r.get("content", "")[:500],
                    "posted_date": r.get("published_date", ""),
                    "source":      "tavily_direct",
                })
            return jobs
        except Exception as e:
            print(f"[job_finder/tavily] {e}")
            return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _infer_company(self, url: str, title: str) -> str:
        def _slug_to_name(slug: str) -> str:
            return " ".join(w.capitalize() for w in re.split(r"[-_]+", slug) if w)

        if not url:
            if title:
                m = re.search(r"\bat\s+([A-Za-z][^\s,|@]{1,40})$", title.strip(), re.IGNORECASE)
                if m:
                    return m.group(1).strip().rstrip(".,")
            return "Unknown Company"

        parsed    = urlparse(url)
        host      = (parsed.hostname or "").lower()
        host_parts = host.split(".")
        path_parts = [p for p in parsed.path.split("/") if p]

        _SKIP = {"jobs", "job", "careers", "career", "apply", "positions", "j", "o"}

        ATS_PATH_IDX = {
            "lever.co": 0, "greenhouse.io": 0, "ashbyhq.com": 0,
            "workable.com": 0, "smartrecruiters.com": 0, "recruitee.com": 0,
            "jobvite.com": 1,
        }
        for domain_frag, idx in ATS_PATH_IDX.items():
            if domain_frag in host and len(path_parts) > idx:
                slug = path_parts[idx]
                if slug.lower() not in _SKIP:
                    return _slug_to_name(slug)

        ATS_SUBDOMAIN = {"bamboohr.com", "breezy.hr", "icims.com"}
        GENERIC_SUB   = {"www", "jobs", "boards", "apply", "hire", "careers", "app"}
        for domain_frag in ATS_SUBDOMAIN:
            if domain_frag in host and host_parts[0] not in GENERIC_SUB:
                return _slug_to_name(host_parts[0])

        CAREER_SUBS = {"careers", "jobs", "job", "hiring", "work", "join", "talent"}
        if len(host_parts) >= 3 and host_parts[0] in CAREER_SUBS and host_parts[1] not in {"co", "com", "net", "org"}:
            return _slug_to_name(host_parts[1])

        if title:
            for pat in (r"\bat\s+([A-Za-z][^\s,|()\[\]]{1,40})$",
                        r"@\s*([A-Za-z][^\s,|()\[\]]{1,40})$"):
                m = re.search(pat, title.strip(), re.IGNORECASE)
                if m:
                    cand = m.group(1).strip().rstrip(".,")
                    if len(cand) > 1:
                        return cand

        CAREER_PATHS = {"jobs", "careers", "career", "join", "openings", "work"}
        if path_parts and path_parts[0].lower() in CAREER_PATHS:
            base = host_parts[0] if host_parts[0] != "www" else (host_parts[1] if len(host_parts) > 1 else "")
            if base:
                return _slug_to_name(base)

        base = host_parts[0] if host_parts[0] != "www" else (host_parts[1] if len(host_parts) > 1 else "")
        if base and not any(agg in base for agg in AGGREGATOR_DOMAINS):
            return _slug_to_name(base)

        for part in path_parts:
            if part.lower() not in _SKIP and len(part) > 2:
                return _slug_to_name(part)

        return "Unknown Company"

    def _deduplicate(self, jobs: list) -> list:
        seen   = set()
        unique = []
        for j in jobs:
            url = j.get("url")
            if url and url not in seen:
                seen.add(url)
                unique.append(j)
        return unique
