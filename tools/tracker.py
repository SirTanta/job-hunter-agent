"""
tools/tracker.py — Persists job application state and history.
SQLite backend. No PostgreSQL required for local dev.

This module is the SINGLE SOURCE OF TRUTH for the database schema.
api.py delegates schema creation here on startup.
"""

import json
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

STATUS_FOUND = "found"
STATUS_RESEARCHED = "researched"
STATUS_APPLIED = "applied"
STATUS_INTERVIEW = "interview"
STATUS_OFFER = "offer"
STATUS_REJECTED = "rejected"
STATUS_WITHDRAWN = "withdrawn"
STATUS_EXPIRED = "expired"

# Default DB path — override via DATABASE_URL env var (sqlite:///path/to/file.db)
_DEFAULT_DB = Path("jobs_tracker.db")


def _db_path() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    return str(_DEFAULT_DB)


class JobTracker:

    def __init__(self):
        path = _db_path()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._create_schema()
        print(f"[DB] Connected to SQLite: {path}")

    def _create_schema(self):
        sql = """
        CREATE TABLE IF NOT EXISTS jobs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            job_title       TEXT,
            company_name    TEXT,
            location        TEXT,
            job_url         TEXT UNIQUE,
            description     TEXT,
            source          TEXT,
            status          TEXT DEFAULT 'found',
            posted_date     TEXT,
            fit_breakdown   TEXT,
            interview_prep  TEXT,
            rejection_text  TEXT,
            rejection_reason TEXT,
            discovered_at   TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS companies (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            name             TEXT UNIQUE,
            website          TEXT,
            overview         TEXT,
            tech_stack       TEXT,
            culture_notes    TEXT,
            glassdoor_rating REAL,
            funding_stage    TEXT,
            recent_news      TEXT,
            company_size     TEXT,
            culture_score    INTEGER,
            red_flags        TEXT,
            why_apply        TEXT,
            fit_score        INTEGER,
            data_quality     TEXT,
            created_at       TEXT DEFAULT (datetime('now')),
            updated_at       TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS applications (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id       INTEGER REFERENCES jobs(id),
            company_id   INTEGER REFERENCES companies(id),
            status       TEXT DEFAULT 'applied',
            applied_at   TEXT DEFAULT (datetime('now')),
            resume_path      TEXT,
            cover_path   TEXT,
            notes        TEXT,
            updated_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS logs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id       TEXT,
            level        TEXT,
            message      TEXT,
            created_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS user_profile (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            name              TEXT,
            experience_level  TEXT,
            job_categories    TEXT,
            preferred_locations TEXT,
            skills            TEXT,
            resume_text       TEXT,
            preferences       TEXT,
            created_at        TEXT DEFAULT (datetime('now')),
            updated_at        TEXT DEFAULT (datetime('now'))
        );
        """
        self.conn.executescript(sql)
        self.conn.commit()

    def save_job(self, job: dict) -> int:
        sql = """
        INSERT INTO jobs (job_title, company_name, location, job_url, description, source)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_url) DO UPDATE SET updated_at = datetime('now')
        RETURNING id;
        """
        cur = self.conn.execute(sql, (
            job.get("job_title"),
            job.get("company_name"),
            job.get("location"),
            job.get("job_url"),
            job.get("description"),
            job.get("source", "unknown"),
        ))
        row = cur.fetchone()
        self.conn.commit()
        return row[0]

    def save_company(self, company: dict) -> int:
        def _to_json(val):
            if isinstance(val, list):
                return json.dumps(val)
            return val

        sql = """
        INSERT INTO companies (
            name, website, overview, tech_stack, culture_notes,
            glassdoor_rating, funding_stage, recent_news,
            company_size, culture_score, red_flags, why_apply,
            fit_score, data_quality, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(name) DO UPDATE SET
            website          = excluded.website,
            overview         = excluded.overview,
            tech_stack       = excluded.tech_stack,
            culture_notes    = excluded.culture_notes,
            glassdoor_rating = excluded.glassdoor_rating,
            funding_stage    = excluded.funding_stage,
            recent_news      = excluded.recent_news,
            company_size     = excluded.company_size,
            culture_score    = excluded.culture_score,
            red_flags        = excluded.red_flags,
            why_apply        = excluded.why_apply,
            fit_score        = excluded.fit_score,
            data_quality     = excluded.data_quality,
            updated_at       = datetime('now')
        RETURNING id;
        """
        cur = self.conn.execute(sql, (
            company.get("name"),
            company.get("website"),
            company.get("overview"),
            _to_json(company.get("tech_stack")),
            company.get("culture_notes"),
            company.get("glassdoor_rating"),
            company.get("funding_stage"),
            _to_json(company.get("recent_news")),
            company.get("company_size"),
            company.get("culture_score"),
            _to_json(company.get("red_flags")),
            company.get("why_apply"),
            company.get("fit_score"),
            company.get("data_quality"),
        ))
        row = cur.fetchone()
        self.conn.commit()
        return row[0]

    def save_application(self, job_id: int, company_id: int = None,
                         resume_path: str = None, cover_path: str = None) -> int:
        sql = """
        INSERT INTO applications (job_id, company_id, resume_path, cover_path)
        VALUES (?, ?, ?, ?)
        RETURNING id;
        """
        cur = self.conn.execute(sql, (job_id, company_id, resume_path, cover_path))
        row = cur.fetchone()
        self.conn.commit()
        return row[0]

    def job_exists(self, job_url: str) -> bool:
        cur = self.conn.execute("SELECT 1 FROM jobs WHERE job_url = ?", (job_url,))
        return cur.fetchone() is not None

    def mark_job_expired(self, job_id: int):
        self.conn.execute(
            "UPDATE jobs SET status = 'expired', updated_at = datetime('now') WHERE id = ?",
            (job_id,)
        )
        self.conn.commit()

    def update_job_status_by_url(self, job_url: str, status: str):
        self.conn.execute(
            "UPDATE jobs SET status = ?, updated_at = datetime('now') WHERE job_url = ?",
            (status, job_url)
        )
        self.conn.commit()

    def update_application_outcome(self, job_url: str, outcome: str, notes: str = ""):
        """Record a response outcome for the feedback loop.
        outcome: 'interview' | 'rejected' | 'offer' | 'no_response'
        """
        self.conn.execute(
            """UPDATE jobs SET status = ?, updated_at = datetime('now') WHERE job_url = ?""",
            (outcome, job_url)
        )
        if notes:
            self.conn.execute(
                """UPDATE applications SET notes = ?, updated_at = datetime('now')
                   WHERE job_id = (SELECT id FROM jobs WHERE job_url = ?)""",
                (notes, job_url)
            )
        self.conn.commit()

    def get_response_stats(self) -> dict:
        """Return feedback loop metrics: response rates by status."""
        cur = self.conn.execute("""
            SELECT status, COUNT(*) as count
            FROM jobs
            WHERE status IN ('applied', 'interview', 'offer', 'rejected', 'manual_review')
            GROUP BY status
        """)
        rows = {r["status"]: r["count"] for r in cur.fetchall()}
        total_applied = sum(rows.get(s, 0) for s in ("applied", "interview", "offer", "rejected"))
        interview_rate = (
            round((rows.get("interview", 0) + rows.get("offer", 0)) / total_applied * 100, 1)
            if total_applied else 0
        )
        return {
            "total_applied": total_applied,
            "interviews": rows.get("interview", 0),
            "offers": rows.get("offer", 0),
            "rejected": rows.get("rejected", 0),
            "manual_review": rows.get("manual_review", 0),
            "interview_rate_pct": interview_rate,
        }

    def get_pending_jobs(self) -> list:
        cur = self.conn.execute(
            "SELECT * FROM jobs WHERE status = 'found' ORDER BY discovered_at DESC"
        )
        return [dict(r) for r in cur.fetchall()]

    def save_daily_report(self, run_id: str, summary: dict) -> int:
        sql = "INSERT INTO logs (run_id, level, message) VALUES (?, 'INFO', ?) RETURNING id;"
        cur = self.conn.execute(sql, (run_id, str(summary)))
        row = cur.fetchone()
        self.conn.commit()
        return row[0]

    def close(self):
        if self.conn:
            self.conn.close()
