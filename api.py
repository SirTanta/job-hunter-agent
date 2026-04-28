import os
import json
import threading
import datetime
import pathlib
import logging
import queue
import uuid
import subprocess
import asyncio
import sqlite3

from typing import Optional

from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────
# CONFIG
# ─────────────────────────────
BASE_DIR = pathlib.Path(__file__).parent.resolve()
PYTHON_EXEC = os.sys.executable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")


# ─────────────────────────────
# DB HELPERS
# ─────────────────────────────
def _db_path() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    return str(BASE_DIR / "jobs_tracker.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ─────────────────────────────
# APP
# ─────────────────────────────
app = FastAPI()
router = APIRouter()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────
# STARTUP — ensure schema exists
# ─────────────────────────────
@app.on_event("startup")
def startup():
    try:
        from tools.tracker import JobTracker
        tracker = JobTracker()
        tracker.close()
        logger.info("SQLite schema ready")
    except Exception as e:
        logger.error(f"DB startup error: {e}")

    # Load profile into CANDIDATE_SUMMARY if one exists
    try:
        conn = get_conn()
        row = conn.execute(
            "SELECT name, experience_level, skills, preferred_locations, job_categories "
            "FROM user_profile ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        if row:
            locs = ", ".join(json.loads(row["preferred_locations"] or "[]"))
            cats = ", ".join(json.loads(row["job_categories"] or "[]"))
            global CANDIDATE_SUMMARY
            CANDIDATE_SUMMARY = (
                f"{row['name']} — {row['experience_level']} level. "
                f"Skills: {row['skills']}. "
                f"Preferred locations: {locs}. "
                f"Looking for: {cats} roles."
            )
            logger.info("CANDIDATE_SUMMARY loaded from user_profile")
    except Exception as e:
        logger.error(f"profile load error: {e}")


# ─────────────────────────────
# ROOT
# ─────────────────────────────
@app.get("/")
def serve_ui():
    return FileResponse(str(BASE_DIR / "index.html"))


# ─────────────────────────────
# STATS
# ─────────────────────────────
@router.get("/stats")
def get_stats():
    try:
        conn = get_conn()
        today = datetime.date.today().isoformat()

        total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        applied_today = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE date(discovered_at) = ?", (today,)
        ).fetchone()[0]
        total_applications = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        total_companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        successful = conn.execute(
            "SELECT COUNT(*) FROM applications WHERE status IN ('interview', 'offer')"
        ).fetchone()[0]
        conn.close()

        success_rate = round(successful / total_applications * 100, 1) if total_applications else 0.0
        return {
            "stats": {
                "total_jobs": total_jobs,
                "applied_today": applied_today,
                "total_applications": total_applications,
                "total_companies": total_companies,
                "success_rate": success_rate,
            }
        }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return {"stats": {"total_jobs": 0, "applied_today": 0,
                          "total_applications": 0, "total_companies": 0,
                          "success_rate": 0.0}}


# ─────────────────────────────
# APPLY TODAY
# ─────────────────────────────
@router.get("/apply-today")
def apply_today():
    try:
        today = datetime.date.today().isoformat()
        conn = get_conn()
        rows = conn.execute("""
            SELECT j.job_title, j.company_name, j.job_url, j.status,
                   a.applied_at, a.status AS app_status
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            WHERE date(a.applied_at) = ?
            ORDER BY a.applied_at DESC
        """, (today,)).fetchall()
        conn.close()
        return {"applications": [dict(r) for r in rows], "count": len(rows), "date": today}
    except Exception as e:
        logger.error(f"apply-today error: {e}")
        return {"applications": [], "count": 0, "date": datetime.date.today().isoformat()}


# ─────────────────────────────
# JOBS
# ─────────────────────────────
@router.get("/jobs")
def get_jobs(
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
    company: Optional[str] = None,
    order_by: str = "discovered_at",
    desc: bool = True,
):
    try:
        conn = get_conn()
        filters = []
        values = []

        if status:
            filters.append("status = ?")
            values.append(status)
        if company:
            filters.append("company_name LIKE ?")
            values.append(f"%{company}%")

        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        direction = "DESC" if desc else "ASC"
        safe_order = order_by if order_by in ("discovered_at", "updated_at", "job_title", "company_name") else "discovered_at"

        jobs = conn.execute(
            f"SELECT * FROM jobs {where} ORDER BY {safe_order} {direction} LIMIT ? OFFSET ?",
            values + [limit, offset],
        ).fetchall()
        total = conn.execute(f"SELECT COUNT(*) FROM jobs {where}", values).fetchone()[0]
        conn.close()

        return {"jobs": [dict(r) for r in jobs], "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        logger.error(f"Jobs error: {e}")
        return {"jobs": [], "total": 0, "limit": limit, "offset": offset}


# ─────────────────────────────
# APPLICATIONS
# ─────────────────────────────
@router.get("/applications")
def get_applications(limit: int = 20, offset: int = 0, status: Optional[str] = None):
    try:
        conn = get_conn()
        filters = []
        values = []

        if status:
            filters.append("a.status = ?")
            values.append(status)

        where = ("WHERE " + " AND ".join(filters)) if filters else ""

        apps = conn.execute(f"""
            SELECT a.*, j.job_title, j.company_name, j.job_url
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            {where}
            ORDER BY a.applied_at DESC
            LIMIT ? OFFSET ?
        """, values + [limit, offset]).fetchall()

        total = conn.execute(
            f"SELECT COUNT(*) FROM applications a {where}", values
        ).fetchone()[0]
        conn.close()

        return {"applications": [dict(r) for r in apps], "total": total}
    except Exception as e:
        logger.error(f"Applications error: {e}")
        return {"applications": [], "total": 0}


# ─────────────────────────────
# FILES
# ─────────────────────────────
@router.get("/files")
def list_files():
    output_dir = BASE_DIR / "output"
    if not output_dir.exists():
        return {"files": []}
    files = []
    for f in sorted(output_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file() and f.suffix in (".docx", ".txt", ".pdf"):
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "modified": datetime.datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
    return {"files": files}


@router.get("/files/{filename}")
def get_file(filename: str):
    target = (BASE_DIR / "output" / filename).resolve()
    if not str(target).startswith(str(BASE_DIR / "output")):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid path")
    if not target.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(target))


# ─────────────────────────────
# RUN STATE
# ─────────────────────────────
RUN_STATE = {
    "status": "idle",
    "run_id": None,
    "logs": [],
    "queue": queue.Queue(),
}


# ─────────────────────────────
# AGENT RUNNER
# ─────────────────────────────
def run_agent_process(run_id: str, limit: int, dry_run: bool):
    RUN_STATE["status"] = "running"
    RUN_STATE["run_id"] = run_id
    RUN_STATE["logs"] = []

    cmd = [PYTHON_EXEC, "agent.py", "--max", str(limit)]
    if dry_run:
        cmd.append("--dry-run")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=BASE_DIR,
        bufsize=1,
        env={**os.environ},
    )

    for line in iter(process.stdout.readline, ""):
        clean = line.strip()
        if clean:
            RUN_STATE["logs"].append(clean)
            RUN_STATE["queue"].put(clean)

    process.stdout.close()
    process.wait()
    RUN_STATE["status"] = "complete"


# ─────────────────────────────
# RUN ENDPOINT
# ─────────────────────────────
class RunRequest(BaseModel):
    mode: str = "full"
    limit: Optional[int] = 5
    dry_run: bool = False


@router.post("/run")
def run_agent(req: RunRequest):
    if RUN_STATE["status"] == "running":
        return {"status": "already_running", "run_id": RUN_STATE["run_id"]}

    run_id = str(uuid.uuid4())
    limit = req.limit or 5

    thread = threading.Thread(
        target=run_agent_process,
        args=(run_id, limit, req.dry_run),
        daemon=True,
    )
    thread.start()

    return {"status": "running", "run_id": run_id}


# ─────────────────────────────
# RUN STATUS
# ─────────────────────────────
@router.get("/run/status")
def run_status():
    return {
        "status": RUN_STATE["status"],
        "run_id": RUN_STATE["run_id"],
        "last_10_lines": RUN_STATE["logs"][-10:],
    }


# ─────────────────────────────
# WEBSOCKET
# ─────────────────────────────
@router.websocket("/ws/logs")
async def websocket_logs(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            while not RUN_STATE["queue"].empty():
                msg = RUN_STATE["queue"].get()
                await ws.send_text(msg)
            await ws.send_text(json.dumps({"type": "heartbeat", "status": RUN_STATE["status"]}))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass


# ─────────────────────────────
# JOB STATUS UPDATE
# ─────────────────────────────
class StatusUpdate(BaseModel):
    status: str


@router.patch("/jobs/{job_id}/status")
async def update_job_status(job_id: int, body: StatusUpdate):
    from fastapi import HTTPException
    allowed = {"found", "applied", "interview", "offer", "rejected"}
    if body.status not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {allowed}")
    try:
        conn = get_conn()
        conn.execute(
            "UPDATE jobs SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (body.status, job_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"success": True, "job": dict(row)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_job_status error: {e}")
        raise


# ─────────────────────────────
# FIT BREAKDOWN
# ─────────────────────────────
from config import CANDIDATE_PROFILE, TARGET_ROLES, JOB_PREFERENCES

def _build_candidate_summary() -> str:
    name = CANDIDATE_PROFILE.get("name", "Candidate")
    summary = CANDIDATE_PROFILE.get("summary", "")
    roles = ", ".join(TARGET_ROLES[:4])
    locs = ", ".join(JOB_PREFERENCES.get("locations", []))
    return f"{name}. {summary} Target roles: {roles}. Locations: {locs}."

CANDIDATE_SUMMARY = _build_candidate_summary()

_FIT_PLACEHOLDER = {"skills": 0, "location": 0, "culture": 0, "seniority": 0, "missing": []}


@router.get("/jobs/{job_id}/fit-breakdown")
async def get_fit_breakdown(job_id: int):
    from fastapi import HTTPException
    try:
        conn = get_conn()
        row = conn.execute(
            "SELECT id, job_title, company_name, location, description, fit_breakdown "
            "FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        conn.close()

        if row is None:
            raise HTTPException(status_code=404, detail="Job not found")

        if row["fit_breakdown"]:
            return {"fit_breakdown": json.loads(row["fit_breakdown"])}

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return {"fit_breakdown": _FIT_PLACEHOLDER}

        job_description = row["description"] or ""
        user_prompt = (
            f"Job title: {row['job_title']}\n"
            f"Company: {row['company_name']}\n"
            f"Location: {row['location'] or 'Not specified'}\n"
            f"Description: {job_description[:2000]}\n\n"
            f"Candidate: {CANDIDATE_SUMMARY}\n\n"
            'Return ONLY a JSON object — no markdown, no explanation:\n'
            '{"skills": 0-10, "location": 0-10, "culture": 0-10, "seniority": 0-10, "missing": ["skill1", "skill2"]}'
        )

        try:
            import anthropic as _anthropic
            client = _anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                system="You are a job fit analyzer. Given a job description and candidate profile, return ONLY valid JSON with no extra text.",
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = message.content[0].text.strip()
            breakdown = json.loads(raw)
        except Exception as e:
            logger.error(f"Claude fit_breakdown call failed: {e}")
            return {"fit_breakdown": _FIT_PLACEHOLDER}

        try:
            conn = get_conn()
            conn.execute(
                "UPDATE jobs SET fit_breakdown = ? WHERE id = ?",
                (json.dumps(breakdown), job_id),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"fit_breakdown cache write failed: {e}")

        return {"fit_breakdown": breakdown}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"fit_breakdown error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─────────────────────────────
# INTERVIEW PREP
# ─────────────────────────────
_INTERVIEW_PLACEHOLDER = {"behavioral": [], "technical": [], "study_checklist": []}


@router.get("/jobs/{job_id}/interview-prep")
async def get_interview_prep(job_id: int):
    from fastapi import HTTPException
    try:
        conn = get_conn()
        row = conn.execute(
            "SELECT id, job_title, company_name, description, interview_prep "
            "FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        conn.close()

        if row is None:
            raise HTTPException(status_code=404, detail="Job not found")

        if row["interview_prep"]:
            return {"interview_prep": json.loads(row["interview_prep"])}

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return {"interview_prep": _INTERVIEW_PLACEHOLDER}

        job_description = row["description"] or ""
        user_prompt = (
            f"Job title: {row['job_title']}\n"
            f"Company: {row['company_name']}\n"
            f"Description: {job_description[:3000]}\n\n"
            f"Candidate: {CANDIDATE_SUMMARY}\n\n"
            "Generate interview prep. Return ONLY a JSON object — no markdown, no explanation:\n"
            '{"behavioral":[{"question":"...","answer_template":"STAR format template..."}],'
            '"technical":[{"question":"...","answer_template":"..."}],'
            '"study_checklist":["topic1","topic2"]}\n'
            "Include 5 behavioral questions with STAR answer templates, "
            "3-5 technical questions relevant to the role, and a study checklist of topics."
        )

        try:
            import anthropic as _anthropic
            client = _anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=2048,
                system="You are an interview coach. Return ONLY valid JSON. Use \\n for newlines inside strings.",
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = message.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0].strip()
            prep = json.loads(raw)
        except json.JSONDecodeError as je:
            logger.error(f"interview_prep JSON parse failed: {je}")
            import re
            try:
                cleaned = re.sub(r'(?<=": ")(.*?)(?="[,\}])', lambda m: m.group(0).replace('\n', '\\n'), raw, flags=re.DOTALL)
                prep = json.loads(cleaned)
            except Exception:
                logger.error("interview_prep salvage parse also failed")
                return {"interview_prep": _INTERVIEW_PLACEHOLDER}
        except Exception as e:
            logger.error(f"Claude interview_prep call failed: {e}")
            return {"interview_prep": _INTERVIEW_PLACEHOLDER}

        try:
            conn = get_conn()
            conn.execute(
                "UPDATE jobs SET interview_prep = ? WHERE id = ?",
                (json.dumps(prep), job_id),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"interview_prep cache write failed: {e}")

        return {"interview_prep": prep}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"interview_prep error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─────────────────────────────
# ONBOARDING
# ─────────────────────────────
class OnboardingRequest(BaseModel):
    name: str
    experience_level: str
    job_categories: list
    preferred_locations: list
    skills: str
    resume_text: Optional[str] = None
    preferences: dict = {}


@router.get("/onboarding")
async def get_onboarding():
    try:
        conn = get_conn()
        row = conn.execute("SELECT * FROM user_profile ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        if not row:
            return {"profile": None}
        d = dict(row)
        for field in ("job_categories", "preferred_locations", "preferences"):
            if isinstance(d.get(field), str):
                try:
                    d[field] = json.loads(d[field])
                except Exception:
                    pass
        return {"profile": d}
    except Exception as e:
        logger.error(f"get_onboarding error: {e}")
        return {"profile": None}


@router.post("/onboarding")
async def save_onboarding(body: OnboardingRequest):
    try:
        conn = get_conn()
        conn.execute("DELETE FROM user_profile")
        conn.execute(
            """INSERT INTO user_profile
               (name, experience_level, job_categories, preferred_locations, skills, resume_text, preferences)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                body.name,
                body.experience_level,
                json.dumps(body.job_categories),
                json.dumps(body.preferred_locations),
                body.skills,
                body.resume_text,
                json.dumps(body.preferences),
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM user_profile ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()

        global CANDIDATE_SUMMARY
        CANDIDATE_SUMMARY = (
            f"{body.name} — {body.experience_level} level. "
            f"Skills: {body.skills}. "
            f"Preferred locations: {', '.join(body.preferred_locations)}. "
            f"Looking for: {', '.join(body.job_categories)} roles."
        )
        logger.info(f"CANDIDATE_SUMMARY updated for {body.name}")

        return {"success": True, "profile": dict(row)}
    except Exception as e:
        logger.error(f"save_onboarding error: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to save profile")


# ─────────────────────────────
# SKILL GAP
# ─────────────────────────────
_SKILL_GAP_EMPTY = {"skills": [], "summary": "Run fit scores on more jobs to see skill gaps."}


@router.get("/skill-gap")
async def get_skill_gap():
    try:
        conn = get_conn()
        rows = conn.execute(
            "SELECT fit_breakdown FROM jobs WHERE fit_breakdown IS NOT NULL"
        ).fetchall()
        conn.close()
    except Exception as e:
        logger.error(f"skill-gap DB error: {e}")
        return {"skill_gap": _SKILL_GAP_EMPTY}

    if not rows:
        return {"skill_gap": _SKILL_GAP_EMPTY}

    skill_counts: dict = {}
    for row in rows:
        fb = row["fit_breakdown"]
        if isinstance(fb, str):
            try:
                fb = json.loads(fb)
            except Exception:
                continue
        for skill in fb.get("missing", []):
            if skill:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1

    if not skill_counts:
        return {"skill_gap": _SKILL_GAP_EMPTY}

    top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"skill_gap": _SKILL_GAP_EMPTY}

    skills_text = "\n".join(f"- {name}: appeared in {count} job(s)" for name, count in top_skills)
    user_prompt = (
        f"Candidate: {CANDIDATE_SUMMARY}\n\n"
        f"Top missing skills from {len(rows)} job fit analyses:\n{skills_text}\n\n"
        "For each skill, estimate demand_score (0-10) and your_score (0-10, candidate's current level). "
        "Include a real learning resource URL and name. Return ONLY a JSON object:\n"
        '{"skills": [{"name": "...", "demand_score": 0-10, "your_score": 0-10, '
        '"resource_url": "https://...", "resource_name": "..."}], '
        '"summary": "One paragraph with key gaps and focus recommendation."}'
    )

    try:
        import anthropic as _anthropic
        client = _anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system="You are a career skills analyst. Return ONLY valid JSON.",
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0].strip()
        skill_gap = json.loads(raw)
    except Exception as e:
        logger.error(f"Claude skill-gap call failed: {e}")
        return {"skill_gap": _SKILL_GAP_EMPTY}

    return {"skill_gap": skill_gap}


# ─────────────────────────────
# GHOST DETECTOR
# ─────────────────────────────
@router.get("/ghost-detector")
async def ghost_detector():
    try:
        conn = get_conn()
        rows = conn.execute("""
            SELECT j.id, j.job_title, j.company_name, j.job_url,
                   CAST(julianday('now') - julianday(a.applied_at) AS INTEGER) AS days_since_applied
            FROM jobs j
            JOIN applications a ON a.job_id = j.id
            WHERE j.status = 'applied'
              AND j.rejection_reason IS NULL
              AND julianday('now') - julianday(a.applied_at) > 7
            GROUP BY j.id
            ORDER BY a.applied_at ASC
        """).fetchall()
        conn.close()
        return {"ghosted_jobs": [dict(r) for r in rows], "total": len(rows)}
    except Exception as e:
        logger.error(f"ghost-detector error: {e}")
        return {"ghosted_jobs": [], "total": 0}


@router.post("/jobs/{job_id}/follow-up")
async def generate_follow_up(job_id: int):
    from fastapi import HTTPException
    try:
        conn = get_conn()
        row = conn.execute("""
            SELECT j.id, j.job_title, j.company_name,
                   CAST(julianday('now') - julianday(a.applied_at) AS INTEGER) AS days_since_applied
            FROM jobs j
            JOIN applications a ON a.job_id = j.id
            WHERE j.id = ?
            ORDER BY a.applied_at ASC LIMIT 1
        """, (job_id,)).fetchone()
        conn.close()

        if row is None:
            raise HTTPException(status_code=404, detail="Job not found")

        days = row["days_since_applied"] or 0
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

        user_prompt = (
            f"Job title: {row['job_title']}\n"
            f"Company: {row['company_name']}\n"
            f"Days since applied: {days}\n"
            f"Candidate: {CANDIDATE_SUMMARY}\n\n"
            "Write a polite, professional follow-up email. Return ONLY a JSON object:\n"
            '{"subject": "...", "body": "..."}'
        )

        try:
            import anthropic as _anthropic
            client = _anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=512,
                system="You are a professional career coach. Write a polite follow-up email. Return ONLY valid JSON.",
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = message.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0].strip()
            follow_up = json.loads(raw)
        except Exception as e:
            logger.error(f"Claude follow-up call failed: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate follow-up email")

        return {"follow_up": follow_up}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"follow-up error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─────────────────────────────
# REJECTION ANALYSIS
# ─────────────────────────────
class RejectionRequest(BaseModel):
    text: Optional[str] = None
    ghost: bool = False


@router.post("/jobs/{job_id}/rejection")
async def submit_rejection(job_id: int, body: RejectionRequest):
    from fastapi import HTTPException
    conn = get_conn()
    row = conn.execute("SELECT id FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    if body.ghost:
        reason = {"category": "ghost", "confidence": 1.0, "explanation": "No response received"}
    else:
        if not body.text:
            raise HTTPException(status_code=400, detail="text is required when ghost is false")

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            reason = {"category": "other", "confidence": 0.5, "explanation": "API key not configured"}
        else:
            user_prompt = (
                f"Candidate: {CANDIDATE_SUMMARY}\n\n"
                f"Rejection message:\n{body.text[:2000]}\n\n"
                "Classify this rejection. Return ONLY a JSON object:\n"
                '{"category": "skills_gap|overqualified|culture_fit|timing|ghost|other", '
                '"confidence": 0.0-1.0, "explanation": "one line reason"}'
            )
            try:
                import anthropic as _anthropic
                client = _anthropic.Anthropic(api_key=api_key)
                message = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=256,
                    system="You are a job rejection analyzer. Return ONLY valid JSON.",
                    messages=[{"role": "user", "content": user_prompt}],
                )
                raw = message.content[0].text.strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[-1]
                if raw.endswith("```"):
                    raw = raw.rsplit("```", 1)[0].strip()
                reason = json.loads(raw)
            except Exception as e:
                logger.error(f"Claude rejection call failed: {e}")
                reason = {"category": "other", "confidence": 0.5, "explanation": "Analysis failed"}

    conn = get_conn()
    conn.execute(
        "UPDATE jobs SET status='rejected', rejection_text=?, rejection_reason=?, updated_at=datetime('now') WHERE id=?",
        (body.text, json.dumps(reason), job_id),
    )
    conn.commit()
    conn.close()
    return {"rejection_reason": reason}


@router.get("/rejection-patterns")
async def get_rejection_patterns():
    try:
        conn = get_conn()
        rows = conn.execute(
            "SELECT rejection_reason FROM jobs WHERE rejection_reason IS NOT NULL"
        ).fetchall()
        conn.close()
    except Exception as e:
        logger.error(f"rejection-patterns DB error: {e}")
        return {"total": 0, "by_category": {}, "meta_analysis": None}

    total = len(rows)
    by_category: dict = {}
    summaries: list = []

    for row in rows:
        rr = row["rejection_reason"]
        if isinstance(rr, str):
            try:
                rr = json.loads(rr)
            except Exception:
                continue
        cat = rr.get("category", "other")
        by_category[cat] = by_category.get(cat, 0) + 1
        summaries.append(f"{cat}: {rr.get('explanation', '')}")

    meta_analysis = None
    if total >= 5:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            summary_text = "\n".join(summaries)
            meta_prompt = (
                f"Here are {total} job rejection classifications for a candidate:\n{summary_text}\n\n"
                "Provide a meta-analysis. Return ONLY a JSON object:\n"
                '{"top_reason": "...", "pattern": "one sentence pattern observed", "recommendation": "one actionable sentence"}'
            )
            try:
                import anthropic as _anthropic
                client = _anthropic.Anthropic(api_key=api_key)
                message = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=256,
                    system="You are a career coach analyzing job rejection patterns. Return ONLY valid JSON.",
                    messages=[{"role": "user", "content": meta_prompt}],
                )
                raw = message.content[0].text.strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[-1]
                if raw.endswith("```"):
                    raw = raw.rsplit("```", 1)[0].strip()
                meta_analysis = json.loads(raw)
            except Exception as e:
                logger.error(f"Claude meta-analysis failed: {e}")

    return {"total": total, "by_category": by_category, "meta_analysis": meta_analysis}


# ─────────────────────────────
# INCLUDE ROUTER
# ─────────────────────────────
app.include_router(router, prefix="/api")

# ─────────────────────────────
# ENTRY
# ─────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
