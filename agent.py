import argparse
import sys
import traceback
from dotenv import load_dotenv

load_dotenv()

from tools.auto_apply import AutoApplier
from tools.company_research import CompanyResearcher
from tools.cover_letter import CoverLetterWriter
from tools.resume_optimizer import ResumeOptimizer
from tools.job_finder import JobFinder
from tools.notion_tracker import NotionTracker
from tools.tracker import JobTracker


class JobHunterAgent:

    def __init__(self, dry_run=False, max_jobs=None, top_n=None, roles=None,
                 locations=None, auto_apply=False):
        self.dry_run = dry_run
        self.auto_apply = auto_apply

        self.limit = max_jobs or top_n or 5

        if top_n and not max_jobs:
            mode_label = f"TOP-{top_n} BY FIT SCORE"
        elif dry_run:
            mode_label = "DRY RUN"
        elif auto_apply:
            mode_label = "FULL RUN + AUTO APPLY"
        else:
            mode_label = "FULL RUN (generate only)"

        print("\n[START] Initialising Job Hunter Agent...")
        print(f"  Mode:      {mode_label}")
        print(f"  Job limit: {self.limit}")

        self.tracker = JobTracker()
        self.notion  = NotionTracker()
        self.job_finder = JobFinder()
        self.researcher = CompanyResearcher(tracker=self.tracker)
        self.resume_optimizer = ResumeOptimizer()
        self.cover_writer = CoverLetterWriter()
        self.applier = AutoApplier(tracker=self.tracker)

        self._stats = {
            "jobs_found": 0,
            "jobs_processed": 0,
            "applications_saved": 0,
            "auto_applied": 0,
            "manual_review": 0,
            "errors": []
        }

    def run(self):
        print("\n[STEP 1] Finding jobs...")
        all_jobs = self.job_finder.search()
        jobs = all_jobs[:self.limit]

        if not jobs:
            print("[WARN] No jobs found")
            return self._stats

        self._stats["jobs_found"] = len(jobs)
        print(f"[INFO] Processing {len(jobs)} jobs")

        for idx, job in enumerate(jobs, 1):
            print(f"\n[{idx}/{len(jobs)}] {job.get('title')} @ {job.get('company')}")

            try:
                # Save to DB
                job_id = self.tracker.save_job({
                    "job_title": job.get("title"),
                    "company_name": job.get("company"),
                    "location": job.get("location"),
                    "job_url": job.get("url"),
                    "description": job.get("description"),
                })
                print(f"[DB] Saved job id={job_id}")

                # Early pre-filter: skip poor-fit JobRight matches before expensive research
                match_score = job.get("match_score")
                if match_score is not None and match_score < 60:
                    print(f"[skip] match_score {match_score}/100 below threshold")
                    self._stats["jobs_processed"] += 1
                    continue

                # Research
                profile = self.researcher.research(
                    company_name=job.get("company"),
                    job_url=job.get("url"),
                    job_title=job.get("title")
                )

                # Generate tailored resume + cover letter (skip if dry run)
                if not self.dry_run:
                    resume_path = self.resume_optimizer.customise(job, profile)
                    cover_path = self.cover_writer.write(job, profile, resume_path)
                    self.tracker.save_application(
                        job_id=job_id,
                        company_id=profile.get("db_id"),
                        resume_path=str(resume_path),
                        cover_path=str(cover_path),
                    )
                    self._stats["applications_saved"] += 1

                    # Auto-apply if enabled
                    if self.auto_apply:
                        result = self.applier.apply(job, resume_path, cover_path, profile)
                        if result["success"]:
                            self._stats["auto_applied"] += 1
                        elif result["method"] == "manual":
                            self._stats["manual_review"] += 1
                        print(f"[apply] {result['method']}: {result['message']}")

                        # Mirror to Notion dashboard
                        self.notion.upsert_application(
                            job=job,
                            apply_result=result,
                            company_profile=profile,
                            resume_path=str(resume_path),
                        )
                    else:
                        # Generate-only mode — still log to Notion as "Applied"
                        self.notion.upsert_application(
                            job=job,
                            apply_result={"success": True, "method": "generated", "job_url": job.get("url", "")},
                            company_profile=profile,
                            resume_path=str(resume_path),
                        )

                self._stats["jobs_processed"] += 1
                print("[OK] Done")

            except Exception as e:
                print(f"[ERROR] {e}")
                self._stats["errors"].append(str(e))

        print("\n[SUMMARY]", self._stats)
        self._print_links_report()
        return self._stats

    def _print_links_report(self):
        """Print all application links to stdout for easy copy-paste."""
        try:
            rows = self.tracker.conn.execute(
                """SELECT j.job_title, j.company_name, j.job_url, j.status,
                          a.resume_path, a.applied_at
                   FROM jobs j
                   LEFT JOIN applications a ON a.job_id = j.id
                   ORDER BY a.applied_at DESC
                   LIMIT 50"""
            ).fetchall()

            if not rows:
                return

            print("\n" + "="*70)
            print("APPLICATION LINKS")
            print("="*70)
            for r in rows:
                title    = r[0] or "?"
                company  = r[1] or "?"
                url      = r[2] or ""
                resume   = r[4] or ""
                resume_f = resume.split("\\")[-1].split("/")[-1] if resume else ""
                print(f"\n  {title} @ {company}")
                if url:
                    print(f"  APPLY: {url}")
                if resume_f:
                    print(f"  RESUME: output/{resume_f}")
            print("="*70)
            print(f"\nNotion Dashboard:")
            print("  https://www.notion.so/Job-Hunt-Dashboard-35084b118b54813a8ef2eca2cf434a03")
        except Exception as e:
            print(f"[links] Could not generate links report: {e}")


def _parse_args():
    parser = argparse.ArgumentParser(description="Job Hunter Agent")
    parser.add_argument("--dry-run", action="store_true",
                        help="Find and research jobs only — no resume generation or applying")
    parser.add_argument("--max", type=int, help="Max number of jobs to process")
    parser.add_argument("--top", type=int, help="Process only the top N jobs by fit score")
    parser.add_argument("--auto-apply", action="store_true",
                        help="Automatically submit applications (LinkedIn Easy Apply / Indeed)")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    try:
        agent = JobHunterAgent(
            dry_run=args.dry_run,
            max_jobs=args.max,
            top_n=args.top,
            auto_apply=args.auto_apply,
        )
        stats = agent.run()
        sys.exit(1 if stats["errors"] else 0)
    except Exception as e:
        print(f"[FATAL] {e}")
        traceback.print_exc()
        sys.exit(1)
