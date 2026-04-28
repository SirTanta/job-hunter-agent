"""
client_hunt/config.py — Tanta Holdings profile for client outreach.

Referenced by pitch_writer.py to anchor pitches with specific proof points
and by apollo_sender.py for sequence configuration.
"""

TANTA_PROFILE = {
    "name":    "Jon Edwards",
    "title":   "AI Enablement Consultant & Instructional Designer",
    "company": "Tanta Holdings LLC",
    "email":   "jedwards@tanta-holdings.com",
    "phone":   "+1 (505) 514-2800",

    "services": [
        "AI enablement curriculum design and delivery",
        "LMS architecture and buildout (from scratch or migration)",
        "Workforce upskilling programs for AI tool adoption",
        "Federal compliance eLearning (508/WCAG, SCORM 1.2/xAPI)",
        "L&D strategy, needs analysis, and program governance",
        "Scenario-based learning and simulation development",
    ],

    # Specific, varied proof points — rotate in pitches for freshness
    "proof_points": [
        "Led FAA systems modernization training at SAIC — translated complex ATC technical systems into SCORM-compliant modules enabling pilot and staff compliance on schedule",
        "3,000+ hours compliance eLearning at the Department of Energy adopted as the national training standard across the DOE National Training Center",
        "Directed Cox Communications Sales Academy redesign — aligned 40+ learning assets to revenue metrics, cut revision cycles 30% via Figma-prototype validation",
        "Built TGA Academy from scratch — full-stack LMS (Next.js, Supabase, SCORM 1.2) with scenario-based capstone simulations, rubric grading, and credential registry",
        "Northrop Grumman: 12 storyboards, 170+ pages, 40+ quick reference guides under strict defense compliance",
        "Presbyterian Healthcare: credentialed Epic EHR trainer delivering blended learning for clinical workflows at scale",
    ],

    # CAN-SPAM footer (inject into pitch body or Apollo sequence template footer)
    "physical_address": (
        "Tanta Holdings LLC | 2020 Rinconada Dr., Rio Rancho, NM 87124"
    ),

    # Target verticals for lead scoring / pitch framing
    "preferred_verticals": [
        "federal/defense",
        "healthcare",
        "energy/utilities",
        "enterprise tech",
        "telecommunications",
        "financial services",
    ],
}

# Apollo sequence to enroll client hunt leads into
# Actual sequence confirmed live: "Tanta Holdings - L&D AI Consulting"
APOLLO_SEQUENCE_NAME = "Tanta Holdings - L&D AI Consulting"

# Sending email account (jedwards@tanta-holdings.com)
# Confirmed live from GET /email_accounts
APOLLO_EMAIL_ACCOUNT_ID = "69e3a240083124001960f9d7"
