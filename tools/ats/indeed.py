"""
tools/ats/indeed.py — Indeed Apply handler (moved from auto_apply.py).
"""
import os
import time
from pathlib import Path
from typing import Optional
from tools.ats.base import BaseATSHandler


class IndeedHandler(BaseATSHandler):

    def submit(self, page, job: dict, cv_path: Optional[Path],
               cover_path: Optional[Path]) -> dict:
        url = job.get("url", "")
        session = os.environ.get("INDEED_SESSION", "")
        if not session:
            return self._manual(url, "No INDEED_SESSION cookie")

        print(f"[indeed] Applying at {url}")
        try:
            for pair in session.split(";"):
                pair = pair.strip()
                if "=" in pair:
                    name, _, val = pair.partition("=")
                    page.context.add_cookies([{
                        "name": name.strip(), "value": val.strip(),
                        "domain": ".indeed.com", "path": "/",
                    }])

            page.goto(url, timeout=20000)
            time.sleep(2)

            apply_btn = page.query_selector(
                "button#indeedApplyButton, "
                "a#applyButtonLinkContainer, "
                "button[data-testid='job-apply-button']"
            )
            if not apply_btn:
                return self._manual(url, "No Apply button found")

            apply_btn.click()
            time.sleep(2)

            self.fill_standard_fields(page)
            self.upload_resume(page, cv_path)
            self.fill_cover_letter(page, cover_path)
            self.answer_all_visible_questions(page)

            submitted = self.submit_loop(page)
            if submitted:
                return self._success("indeed_apply", url)
            return self._manual(url, "Submit flow incomplete")
        except Exception as e:
            return self._manual(url, str(e))
