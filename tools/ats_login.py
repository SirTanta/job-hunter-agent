"""
tools/ats_login.py — ATS account login flows.

Handles login for ATS systems that require an account before applying.
Most modern ATS (Lever, Greenhouse, Ashby) support guest apply — no login needed.
Login is required for: Workday, iCIMS, Taleo, Indeed (full apply), some SmartRecruiters.

All credentials loaded from environment:
  ATS_EMAIL        — jedwar82@gmail.com (default apply email)
  ATS_PASSWORD     — primary password
  WORKDAY_EMAIL    — Workday-specific (may differ)
  WORKDAY_PASSWORD — Workday-specific

The email monitor is passed in so login flows can capture OTPs automatically.
"""

import os
import time
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page
    from tools.email_monitor import EmailMonitor


ATS_EMAIL    = os.environ.get("ATS_EMAIL",    "jedwar82@gmail.com")
ATS_PASSWORD = os.environ.get("ATS_PASSWORD", "")


class ATSLoginManager:
    """
    Handles login for ATS systems that require authentication.
    Passes through email_monitor to capture 2FA/OTP codes in real time.
    """

    def __init__(self, email_monitor=None):
        self.monitor = email_monitor

    # ------------------------------------------------------------------
    # Workday
    # ------------------------------------------------------------------

    def login_workday(self, page, ctx) -> bool:
        """
        Log into Workday at the sign-in page.
        Workday accounts are global — one account works across all companies.

        Returns True on success.
        """
        email    = os.environ.get("WORKDAY_EMAIL",    ATS_EMAIL)
        password = os.environ.get("WORKDAY_PASSWORD", ATS_PASSWORD)

        if not password:
            print("[login] No WORKDAY_PASSWORD — will attempt guest apply")
            return False

        try:
            # Workday sign-in URL pattern
            signin_url = "https://www.myworkday.com/wday/authgwy/signinwithworkdayaccount"
            page.goto(signin_url, timeout=20000)
            time.sleep(2)

            email_field = page.query_selector("input[type='email'], input[id*='email' i]")
            if email_field:
                email_field.fill(email)

            next_btn = page.query_selector("button:has-text('Next'), button:has-text('Continue')")
            if next_btn:
                next_btn.click()
                time.sleep(1.5)

            password_field = page.query_selector("input[type='password']")
            if password_field:
                password_field.fill(password)
                password_field.press("Enter")
                time.sleep(2)

            # Handle OTP if Workday sends one
            otp_field = page.query_selector(
                "input[id*='otp' i], input[placeholder*='code' i], "
                "input[id*='verification' i]"
            )
            if otp_field:
                print("[login] Workday sent OTP — waiting for email...")
                code = self._get_otp(sender_filter="workday")
                if code:
                    otp_field.fill(code)
                    otp_field.press("Enter")
                    time.sleep(2)

            # Check if logged in
            if "myworkday.com" in page.url and "signin" not in page.url:
                print("[login] Workday login successful")
                return True

            print("[login] Workday login unclear — proceeding anyway")
            return True

        except Exception as e:
            print(f"[login] Workday login error: {e}")
            return False

    # ------------------------------------------------------------------
    # iCIMS
    # ------------------------------------------------------------------

    def login_icims(self, page, company_url: str) -> bool:
        """
        iCIMS is company-specific — each company has their own iCIMS instance.
        Most allow guest apply. We only login if required.
        """
        password = ATS_PASSWORD
        if not password:
            return False

        try:
            # Navigate to the company's iCIMS login page
            login_url = company_url.split("/jobs")[0] + "/login"
            page.goto(login_url, timeout=15000)
            time.sleep(2)

            email_field = page.query_selector("input[type='email'], input[name*='email' i]")
            pass_field  = page.query_selector("input[type='password']")

            if email_field and pass_field:
                email_field.fill(ATS_EMAIL)
                pass_field.fill(password)
                page.query_selector("button[type='submit'], input[type='submit']").click()
                time.sleep(2)
                return True

            return False
        except Exception as e:
            print(f"[login] iCIMS login error: {e}")
            return False

    # ------------------------------------------------------------------
    # SmartRecruiters
    # ------------------------------------------------------------------

    def login_smartrecruiters(self, page) -> bool:
        """SmartRecruiters allows guest apply — login only if prompted."""
        password = ATS_PASSWORD
        if not password:
            return False

        try:
            page.goto("https://jobs.smartrecruiters.com/login", timeout=15000)
            time.sleep(2)
            email_f = page.query_selector("input[type='email']")
            pass_f  = page.query_selector("input[type='password']")
            if email_f and pass_f:
                email_f.fill(ATS_EMAIL)
                pass_f.fill(password)
                page.query_selector("button[type='submit']").click()
                time.sleep(2)
                return True
            return False
        except Exception as e:
            print(f"[login] SmartRecruiters login error: {e}")
            return False

    # ------------------------------------------------------------------
    # Generic login (email + password form)
    # ------------------------------------------------------------------

    def login_generic(self, page, login_url: str) -> bool:
        """
        Attempt a generic email+password login.
        Used for any ATS that follows the standard pattern.
        """
        password = ATS_PASSWORD
        if not password:
            return False

        try:
            page.goto(login_url, timeout=15000)
            time.sleep(2)

            email_f = page.query_selector("input[type='email'], input[name*='email' i]")
            pass_f  = page.query_selector("input[type='password']")

            if not email_f or not pass_f:
                return False

            email_f.fill(ATS_EMAIL)
            pass_f.fill(password)

            submit = page.query_selector(
                "button[type='submit'], input[type='submit'], "
                "button:has-text('Sign in'), button:has-text('Log in')"
            )
            if submit:
                submit.click()
                time.sleep(2)

            # Check for OTP field
            otp = page.query_selector(
                "input[id*='otp' i], input[placeholder*='code' i], "
                "input[name*='verification' i], input[autocomplete='one-time-code']"
            )
            if otp:
                code = self._get_otp()
                if code:
                    otp.fill(code)
                    otp.press("Enter")
                    time.sleep(2)

            return True

        except Exception as e:
            print(f"[login] Generic login error: {e}")
            return False

    # ------------------------------------------------------------------
    # Handle "enter your email to continue" gates
    # ------------------------------------------------------------------

    def handle_email_gate(self, page) -> bool:
        """
        Some ATS show a modal/page asking for your email before showing the form.
        Enter the email and handle any verification that follows.
        """
        gate = page.query_selector(
            "input[placeholder*='Enter your email' i], "
            "input[placeholder*='Email address' i][data-modal], "
            "div.email-gate input[type='email']"
        )
        if not gate:
            return False

        gate.fill(ATS_EMAIL)
        gate_submit = page.query_selector("button:near(input[type='email'])")
        if gate_submit:
            gate_submit.click()
            time.sleep(1.5)

        # Check for OTP field that appears after email submission
        otp = page.query_selector(
            "input[autocomplete='one-time-code'], "
            "input[placeholder*='verification code' i], "
            "input[placeholder*='6-digit' i]"
        )
        if otp:
            print("[login] Email gate sent OTP — waiting...")
            code = self._get_otp()
            if code:
                otp.fill(code)
                otp.press("Enter")
                time.sleep(2)
                return True

        return True

    # ------------------------------------------------------------------
    # OTP helper
    # ------------------------------------------------------------------

    def _get_otp(self, timeout: int = 90, sender_filter: str = None) -> Optional[str]:
        """
        Get an OTP code from the email monitor.
        If monitor isn't running, start it for this call only.
        """
        if self.monitor and self.monitor._conn:
            # Apply sender_filter even when monitor is already running
            if sender_filter:
                self.monitor._sender_filter = sender_filter
            return self.monitor.wait_for_code(timeout=timeout)

        # One-shot: start monitor just for this OTP
        from tools.email_monitor import EmailMonitor
        with EmailMonitor() as monitor:
            if sender_filter:
                monitor._sender_filter = sender_filter
            return monitor.wait_for_code(timeout=timeout)
