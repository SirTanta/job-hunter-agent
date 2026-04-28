"""
tools/ats/smartrecruiters.py — SmartRecruiters ATS handler.
URL: jobs.smartrecruiters.com/{Company}/{id}
"""
import time
from pathlib import Path
from typing import Optional
from tools.ats.base import BaseATSHandler


class SmartRecruitersHandler(BaseATSHandler):

    def submit(self, page, job: dict, resume_path: Optional[Path],
               cover_path: Optional[Path]) -> dict:
        url = job.get("url", "")
        print(f"[smartrecruiters] Applying at {url}")
        try:
            page.goto(url, timeout=20000)
            time.sleep(2)

            apply_btn = page.query_selector(
                "a.ats-apply-button, button:has-text('Apply Now'), "
                "a:has-text('Apply'), button.js-apply-btn"
            )
            if apply_btn:
                apply_btn.click()
                time.sleep(1.5)

            self.fill_standard_fields(page)
            self.upload_resume(page, resume_path)
            self.fill_cover_letter(page, cover_path)
            self.answer_all_visible_questions(page)

            submitted = self.submit_loop(page)
            if submitted:
                return self._success("smartrecruiters", url)
            return self._manual(url, "Submit flow incomplete")
        except Exception as e:
            return self._manual(url, str(e))
