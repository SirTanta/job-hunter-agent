"""
tools/ats/workday.py — Workday ATS handler (rewritten).

Key fixes over v1:
  1. New-tab / popup handling — Workday opens new windows for login,
     file previews, and SSO. We capture them with context.expect_page().
  2. Account login support via ATSLoginManager
  3. Real-time OTP capture via EmailMonitor when Workday sends a code
  4. Guest apply path (no account required on many Workday instances)
  5. Robust step loop that re-scans for questions each step

URL pattern: {company}.wd{n}.myworkdayjobs.com/en-US/{site}/job/{title}/{id}
"""

import os
import time
from pathlib import Path
from typing import Optional

from tools.ats.base import BaseATSHandler, _fill_if_present
from tools.ats_login import ATSLoginManager


class WorkdayHandler(BaseATSHandler):

    def __init__(self, tracker=None, email_monitor=None):
        super().__init__(tracker=tracker)
        self.email_monitor = email_monitor
        self.login_mgr = ATSLoginManager(email_monitor=email_monitor)

    def submit(self, page, job: dict, resume_path: Optional[Path],
               cover_path: Optional[Path]) -> dict:
        url = job.get("url", "")
        ctx = page.context
        print(f"[workday] Applying at {url}")

        try:
            page.goto(url, timeout=25000)
            time.sleep(3)

            # ── Find Apply button ─────────────────────────────────────
            apply_btn = page.query_selector(
                "a[data-automation-id='applyButton'], "
                "button[data-automation-id='applyButton'], "
                "a:has-text('Apply'), "
                "button:has-text('Apply Now')"
            )
            if not apply_btn:
                return self._manual(url, "No Apply button found")

            # Watch for new tab/popup BEFORE clicking apply
            # Workday sometimes opens a new window for the application
            with ctx.expect_page(timeout=5000) as new_page_info:
                apply_btn.click()
                time.sleep(1)

            try:
                app_page = new_page_info.value
                app_page.wait_for_load_state("domcontentloaded", timeout=15000)
                print("[workday] Application opened in new tab")
            except Exception:
                # No new tab opened — apply happened inline
                app_page = page

            time.sleep(2)

            # ── Handle login / guest flow ─────────────────────────────
            app_page = self._handle_auth_flow(app_page, ctx, url)

            # ── Resume upload (Workday parses it to pre-fill fields) ──
            self.upload_resume(app_page, resume_path)
            time.sleep(2)

            # ── Step-by-step wizard ───────────────────────────────────
            submitted = self._workday_wizard(app_page, ctx, resume_path, cover_path)

            if submitted:
                return self._success("workday", url)
            return self._manual(url, "Workday wizard did not reach confirmation")

        except Exception as e:
            print(f"[workday] Error: {e}")
            import traceback
            traceback.print_exc()
            return self._manual(url, str(e))

    # ------------------------------------------------------------------
    # Auth flow
    # ------------------------------------------------------------------

    def _handle_auth_flow(self, page, ctx, original_url: str):
        """
        Handle Workday's auth options:
          A) Guest apply (no account needed) — most common
          B) Sign in with existing Workday account
          C) Create new account

        Returns the page to continue working on (may be the same page).
        """
        time.sleep(1)

        # Option A: "Apply Manually" / "Continue as Guest"
        for sel in (
            "button:has-text('Apply Manually')",
            "a:has-text('Apply Manually')",
            "button:has-text('Continue as Guest')",
            "button:has-text('Skip Sign In')",
            "button[data-automation-id='applyManually']",
        ):
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                time.sleep(1.5)
                print("[workday] Using guest apply path")
                return page

        # Option B: Sign in with Workday account
        workday_password = os.environ.get("WORKDAY_PASSWORD", "")
        if workday_password:
            sign_in = page.query_selector(
                "button:has-text('Sign In'), a:has-text('Sign In with Workday')"
            )
            if sign_in:
                # Sign-in may open a new tab
                try:
                    with page.context.expect_page(timeout=4000) as p:
                        sign_in.click()
                    auth_page = p.value
                    auth_page.wait_for_load_state("domcontentloaded", timeout=10000)
                except Exception:
                    auth_page = page

                self._fill_workday_credentials(auth_page)

                # After login, we may be redirected back to the application
                time.sleep(2)
                # Switch back to application page if auth was on a separate tab
                pages = page.context.pages
                app_page = pages[-1] if len(pages) > 1 else page
                return app_page

        # Check for email gate (enter email to begin)
        self.login_mgr.handle_email_gate(page)
        return page

    def _fill_workday_credentials(self, page) -> None:
        """Fill Workday sign-in form on the auth page."""
        email    = os.environ.get("WORKDAY_EMAIL",    os.environ.get("ATS_EMAIL", ""))
        password = os.environ.get("WORKDAY_PASSWORD", "")

        _fill_if_present(page, ["input[type='email'], input[name*='email' i]"], email)
        time.sleep(0.3)

        next_btn = page.query_selector("button:has-text('Next'), button:has-text('Continue')")
        if next_btn:
            next_btn.click()
            time.sleep(1)

        _fill_if_present(page, ["input[type='password']"], password)
        page.keyboard.press("Enter")
        time.sleep(2)

        # Check for Workday OTP
        otp_field = page.query_selector(
            "input[autocomplete='one-time-code'], "
            "input[placeholder*='code' i], "
            "input[id*='otp' i]"
        )
        if otp_field:
            print("[workday] Sign-in sent OTP — waiting for email...")
            code = self.login_mgr._get_otp(sender_filter="workday")
            if code:
                otp_field.fill(code)
                otp_field.press("Enter")
                time.sleep(2)

    # ------------------------------------------------------------------
    # Wizard loop
    # ------------------------------------------------------------------

    def _workday_wizard(self, page, ctx, resume_path, cover_path,
                        max_steps: int = 20) -> bool:
        """
        Navigate Workday's step wizard.
        Steps vary by company but typically:
          My Information → My Experience → Application Questions →
          Voluntary Disclosures → Review → Submit
        """
        SUBMIT_SELECTORS = [
            "button[data-automation-id='bottom-navigation-next-btn']:has-text('Submit')",
            "button[aria-label='Submit']:not([disabled])",
            "button:has-text('Submit'):not([disabled])",
        ]
        NEXT_SELECTORS = [
            "button[data-automation-id='bottom-navigation-next-btn']",
            "button:has-text('Save and Continue')",
            "button:has-text('Next')",
            "button[aria-label='Next']",
        ]
        CONFIRM_SELECTORS = [
            "[data-automation-id='confirmationSection']",
            "h2:has-text('Application Submitted')",
            "h1:has-text('Thank you for applying')",
            ":has-text('Your application has been submitted')",
        ]

        for step in range(max_steps):
            time.sleep(2)

            # Watch for new tab opened by Workday mid-flow
            # (e.g. SSO redirect, document preview)
            current_pages = page.context.pages
            if len(current_pages) > 1:
                newest = current_pages[-1]
                if newest != page and newest.url != "about:blank":
                    print(f"[workday] New tab detected: {newest.url[:60]}")
                    # Close it and continue on the application page
                    try:
                        newest.close()
                    except Exception:
                        pass

            # Check for confirmation
            for sel in CONFIRM_SELECTORS:
                try:
                    if page.query_selector(sel):
                        print(f"[workday] Confirmed at step {step+1}")
                        return True
                except Exception:
                    pass

            # Fill the current step's contact fields
            self._fill_workday_fields(page)

            # Answer custom questions on this step
            self._answer_workday_questions(page)

            # Cover letter (Application Questions step)
            if cover_path:
                self.fill_cover_letter(page, cover_path)

            # Try submit
            for sel in SUBMIT_SELECTORS:
                btn = page.query_selector(sel)
                if btn and btn.is_visible() and not btn.is_disabled():
                    print(f"[workday] Clicking Submit at step {step+1}")
                    btn.click()
                    time.sleep(3)

                    # After submit, check for post-submit OTP (some Workday flows send one)
                    otp_field = page.query_selector("input[autocomplete='one-time-code']")
                    if otp_field:
                        code = self.login_mgr._get_otp(sender_filter="workday")
                        if code:
                            otp_field.fill(code)
                            otp_field.press("Enter")
                            time.sleep(2)

                    return True

            # Try next
            advanced = False
            for sel in NEXT_SELECTORS:
                btn = page.query_selector(sel)
                if btn and btn.is_visible() and not btn.is_disabled():
                    print(f"[workday] Next at step {step+1}")
                    btn.click()
                    advanced = True
                    break

            if not advanced:
                print(f"[workday] No actionable button at step {step+1} — stopping")
                break

        return False

    # ------------------------------------------------------------------
    # Field filling
    # ------------------------------------------------------------------

    def _fill_workday_fields(self, page) -> None:
        """Fill Workday-specific contact field IDs."""
        p = self.profile

        _fill_if_present(page, [
            "input[data-automation-id='legalNameSection_firstName']",
            "input[aria-label='First Name']",
        ], p.get("name", "").split()[0])

        _fill_if_present(page, [
            "input[data-automation-id='legalNameSection_lastName']",
            "input[aria-label='Last Name']",
        ], p.get("name", "").split()[-1])

        _fill_if_present(page, [
            "input[data-automation-id='email']",
            "input[data-automation-id='addressSection_email']",
            "input[type='email']",
        ], p.get("email", ""))

        _fill_if_present(page, [
            "input[data-automation-id='phone-number']",
            "input[data-automation-id='addressSection_phone']",
        ], p.get("phone", ""))

        _fill_if_present(page, [
            "input[data-automation-id='city']",
            "input[aria-label='City']",
        ], "Rio Rancho")

        time.sleep(0.3)

    def _answer_workday_questions(self, page) -> None:
        """Answer Workday custom application questions."""
        import re

        # Text inputs with labels
        for label_el in page.query_selector_all("label"):
            question = label_el.inner_text().strip()
            if not question or len(question) < 5:
                continue

            for_id = label_el.get_attribute("for")
            field = page.query_selector(f"#{for_id}") if for_id else None
            if not field:
                field = label_el.query_selector("input, textarea")
            if not field:
                continue

            tag = field.evaluate("el => el.tagName.toLowerCase()")
            ftype = field.get_attribute("type") or tag
            if ftype in ("hidden", "file", "submit", "button"):
                continue

            try:
                current = field.input_value()
                if current and len(current) > 2:
                    continue
            except Exception:
                pass

            if tag == "textarea":
                answer = self.answer_question(question, "textarea")
                field.fill(answer)
            elif ftype in ("text", "number"):
                answer = self.answer_question(question, "text")
                field.fill(answer)

        # Workday custom dropdown components (not native <select>)
        for dropdown in page.query_selector_all(
            "div[data-automation-id*='promptOption'], "
            "button[data-automation-id*='selectWidget']"
        ):
            label_el = dropdown.query_selector("label, legend, .WCUX-label")
            if not label_el:
                continue
            question = label_el.inner_text().strip()
            if not question:
                continue

            try:
                dropdown.click()
                time.sleep(0.5)
                options = [
                    o.inner_text().strip()
                    for o in page.query_selector_all("[role='option'], [data-automation-id*='listItem']")
                    if o.inner_text().strip()
                ]
                if options:
                    answer = self.answer_question(question, "select", options)
                    for opt in page.query_selector_all("[role='option']"):
                        if opt.inner_text().strip() == answer:
                            opt.click()
                            break
                    else:
                        page.keyboard.press("Escape")
            except Exception:
                pass
