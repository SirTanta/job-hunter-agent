"""
tools/ats/__init__.py — ATS detection and handler routing.

Detects which ATS a job URL belongs to and returns the correct handler.
Falls back to the Claude-powered generic handler for unknown systems.
"""

import re
from urllib.parse import urlparse


# ── ATS URL pattern registry ──────────────────────────────────────────────────
# Each entry: (regex_pattern, ats_name, handler_module)
# Ordered by specificity — first match wins.

ATS_PATTERNS = [
    # LinkedIn
    (r"linkedin\.com/jobs",                  "linkedin",         "linkedin"),
    # Indeed
    (r"indeed\.com",                         "indeed",           "indeed"),
    # Lever
    (r"jobs\.lever\.co",                     "lever",            "lever"),
    # Greenhouse
    (r"boards\.greenhouse\.io",              "greenhouse",       "greenhouse"),
    (r"app\.greenhouse\.io",                 "greenhouse",       "greenhouse"),
    (r"greenhouse\.io/job_board",            "greenhouse",       "greenhouse"),
    # Ashby
    (r"jobs\.ashbyhq\.com",                  "ashby",            "ashby"),
    (r"ashbyhq\.com",                        "ashby",            "ashby"),
    # Workday
    (r"myworkdayjobs\.com",                  "workday",          "workday"),
    (r"wd\d+\.myworkdayjobs\.com",           "workday",          "workday"),
    # SmartRecruiters
    (r"jobs\.smartrecruiters\.com",          "smartrecruiters",  "smartrecruiters"),
    (r"smartrecruiters\.com/post",           "smartrecruiters",  "smartrecruiters"),
    # BambooHR
    (r"bamboohr\.com/careers",              "bamboohr",         "bamboohr"),
    (r"\.bamboohr\.com",                     "bamboohr",         "bamboohr"),
    # iCIMS
    (r"icims\.com",                          "icims",            "generic"),
    # Taleo / Oracle
    (r"taleo\.net",                          "taleo",            "generic"),
    (r"oracle\.taleo\.net",                  "taleo",            "generic"),
    # Jobvite
    (r"jobs\.jobvite\.com",                  "jobvite",          "generic"),
    # Breezy HR
    (r"breezy\.hr",                          "breezy",           "generic"),
    # Recruitee
    (r"recruitee\.com",                      "recruitee",        "generic"),
    # Rippling
    (r"jobs\.rippling\.com",                 "rippling",         "generic"),
    # Wellfound / AngelList
    (r"wellfound\.com",                      "wellfound",        "generic"),
    (r"angel\.co/jobs",                      "wellfound",        "generic"),
    # Workable
    (r"apply\.workable\.com",                "workable",         "generic"),
    # JazzHR
    (r"app\.jazz\.hr",                       "jazzhr",           "generic"),
    # Pinpoint
    (r"pinpointhq\.com",                     "pinpoint",         "generic"),
    # Comeet
    (r"comeet\.com",                         "comeet",           "generic"),
    # HiringThing
    (r"hiringthing\.com",                    "hiringthing",      "generic"),
]


def detect_ats(url: str) -> tuple[str, str]:
    """
    Returns (ats_name, handler_module) for the given job URL.
    Falls back to ("generic", "generic") for unknown systems.
    """
    if not url:
        return ("generic", "generic")

    url_lower = url.lower()
    for pattern, ats_name, handler in ATS_PATTERNS:
        if re.search(pattern, url_lower):
            return (ats_name, handler)

    return ("generic", "generic")


def get_handler(url: str, **kwargs):
    """
    Instantiate and return the correct ATS handler for a URL.
    All handlers share the same constructor signature.
    """
    ats_name, module_name = detect_ats(url)

    # Import the right handler module
    if module_name == "linkedin":
        from tools.ats.linkedin import LinkedInHandler
        return LinkedInHandler(**kwargs)
    elif module_name == "indeed":
        from tools.ats.indeed import IndeedHandler
        return IndeedHandler(**kwargs)
    elif module_name == "lever":
        from tools.ats.lever import LeverHandler
        return LeverHandler(**kwargs)
    elif module_name == "greenhouse":
        from tools.ats.greenhouse import GreenhouseHandler
        return GreenhouseHandler(**kwargs)
    elif module_name == "ashby":
        from tools.ats.ashby import AshbyHandler
        return AshbyHandler(**kwargs)
    elif module_name == "workday":
        from tools.ats.workday import WorkdayHandler
        return WorkdayHandler(**kwargs)
    elif module_name == "smartrecruiters":
        from tools.ats.smartrecruiters import SmartRecruitersHandler
        return SmartRecruitersHandler(**kwargs)
    elif module_name == "bamboohr":
        from tools.ats.bamboohr import BambooHRHandler
        return BambooHRHandler(**kwargs)
    else:
        from tools.ats.generic import GenericHandler
        return GenericHandler(ats_name=ats_name, **kwargs)
