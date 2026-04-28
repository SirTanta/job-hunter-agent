"""
tools/ats/workday.py — Workday ATS handler.

Workday is the most complex ATS. It requires a Workday account or guest apply.
URL pattern: {company}.wd{n}.myworkdayjobs.com/en-US/{site}/job/{title}/{id}

Strategy:
  1. Click "Apply" to start
  2. Handle "Apply with Workday" or guest flow
  3. Multi-step wizard with dynamic sections
  4. Use Claude to answer all custom questions
"""

import time
from pathlib import Path
from typing import Optional

from tools.ats.base import BaseATSHandler, _fill_if_present


class WorkdayHandler(BaseATSHandler):

    def submit(self, page, job: dict, cv_path: Optional[Path],
               cover_path: Optional[Path]) -> dict:
        url = job.get("url", "")
        print(f"[workday] Applying at {url}")

        try:
            page.goto(url, timeout=25000)
            time.sleep(3)

            # Find and click Apply button
            apply_btn = page.query_selector(
                "a[data-automation-id='applyButton'], "
                "button[data-automation-id='applyButton'], "
                "a:has-text('Apply'), "
                "button:has-text('Apply Now')"
            )
            if not apply_btn:
                return self._manual(url, "No Apply button found")

            apply_btn.click()
            time.sleep(2)

            # Handle "Apply Manually" vs "Apply with Workday account"
            # Prefer guest/manual flow to avoid account requirements
            manual_btn = page.query_selector(
                "button:has-text('Apply Manually'), "
                "a:has-text('Apply Manually'), "
                "button[data-automation-id='applyManually']"
            )
            if manual_btn:
                manual_btn.click()
                time.sleep(1.5)

            # Step 1: My Information
            self._fill_workday_contact(page)

            # Step 2: Resume upload
            self.upload_resume(page, cv_path)
            time.sleep(1)

            # Navigate through all steps using the submit loop
            # Workday has: My Information → Experience → Application Questions → Self Identify → Review
            submitted = self._workday_step_loop(page, cv_path, cover_path)

            if submitted:
                return self._success("workday", url)
            return self._manual(url, "Workday submit flow incomplete — check manually")

        except Exception as e:
            print(f"[workday] Error: {e}")
            return self._manual(url, str(e))

    def _fill_workday_contact(self, page) -> None:
        """Fill Workday's specific contact field IDs."""
        p = self.profile

        _fill_if_present(page, [
            "input[data-automation-id='legalNameSection_firstName']",
            "input[aria-label*='First Name' i]",
        ], p.get("name", "").split()[0])

        _fill_if_present(page, [
            "input[data-automation-id='legalNameSection_lastName']",
            "input[aria-label*='Last Name' i]",
        ], p.get("name", "").split()[-1])

        _fill_if_present(page, [
            "input[data-automation-id='email']",
            "input[type='email']",
        ], p.get("email", ""))

        _fill_if_present(page, [
            "input[data-automation-id='phone-number']",
            "input[type='tel']",
        ], p.get("phone", ""))

        _fill_if_present(page, [
            "input[data-automation-id='city']",
            "input[aria-label*='City' i]",
        ], "Rio Rancho")

        time.sleep(0.5)

    def _workday_step_loop(self, page, cv_path, cover_path, max_steps: int = 15) -> bool:
        """Navigate Workday's multi-step wizard, answering questions at each step."""
        NEXT_SELECTORS = [
            "button[data-automation-id='bottom-navigation-next-btn']",
            "button:has-text('Next')",
            "button:has-text('Save and Continue')",
            "button[aria-label*='next' i]",
        ]
        SUBMIT_SELECTORS = [
            "button[data-automation-id='bottom-navigation-next-btn']:has-text('Submit')",
            "button:has-text('Submit')",
            "button[aria-label*='Submit' i]",
        ]
        CONFIRM_SELECTORS = [
            "[data-automation-id='confirmationSection']",
            ":has-text('Application Submitted')",
            ":has-text('Thank you for applying')",
        ]

        for step in range(max_steps):
            time.sleep(2)

            # Check confirmation
            for sel in CONFIRM_SELECTORS:
                try:
                    if page.query_selector(sel):
                        return True
                except Exception:
                    pass

            # Answer visible questions
            try:
                self._answer_workday_questions(page)
            except Exception:
                pass

            # Cover letter text area (appears on Application Questions step)
            if cover_path:
                self.fill_cover_letter(page, cover_path)

            # Try submit first
            for sel in SUBMIT_SELECTORS:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    time.sleep(3)
                    return True

            # Try next
            advanced = False
            for sel in NEXT_SELECTORS:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    advanced = True
                    break

            if not advanced:
                break

        return False

    def _answer_workday_questions(self, page) -> None:
        """Answer Workday's custom application questions."""
        # Workday renders questions in fieldsets with data-automation-id
        questions = page.query_selector_all(
            "[data-automation-id*='formField'], "
            "div.css-1jbu4yk, "  # Workday's question container class
            "fieldset"
        )
        for q_el in questions:
            label_el = q_el.query_selector("label, legend")
            if not label_el:
                continue
            question_text = label_el.inner_text().strip()
            if not question_text or len(question_text) < 5:
                continue

            # Text inputs
            text_field = q_el.query_selector("input[type='text'], input[type='number']")
            if text_field:
                current = text_field.input_value()
                if not current or len(current) < 2:
                    answer = self.answer_question(question_text, "text")
                    text_field.fill(answer)
                continue

            # Textareas
            textarea = q_el.query_selector("textarea")
            if textarea:
                current = textarea.input_value()
                if not current or len(current) < 2:
                    answer = self.answer_question(question_text, "textarea")
                    textarea.fill(answer)
                continue

            # Dropdowns (Workday uses custom select components)
            dropdown_btn = q_el.query_selector(
                "button[data-automation-id*='select'], "
                "[aria-haspopup='listbox']"
            )
            if dropdown_btn:
                # Get options by clicking the dropdown
                try:
                    dropdown_btn.click()
                    time.sleep(0.5)
                    option_els = page.query_selector_all(
                        "[role='option'], li[data-automation-id*='option']"
                    )
                    options = [o.inner_text().strip() for o in option_els if o.inner_text().strip()]
                    if options:
                        answer = self.answer_question(question_text, "select", options)
                        for opt_el in option_els:
                            if opt_el.inner_text().strip() == answer:
                                opt_el.click()
                                break
                        else:
                            # Close dropdown if no match
                            page.keyboard.press("Escape")
                except Exception:
                    pass
