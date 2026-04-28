# config.py — Candidate profile, job preferences, and agent configuration

CANDIDATE_PROFILE = {
    "name": "Jon Edwards, M.Ed",
    "location": "Rio Rancho, NM, USA",
    "email": "jon.edwards.jobs@outlook.com",
    "phone": "+1 (505) 514-2800",
    "linkedin": "linkedin.com/in/jedwar82/",
    "github": "",
    "portfolio": "https://www.tantaholdings.com/solutions/portfolio",

    "summary": (
        "Senior-level Learning & Development professional with expertise delivering "
        "clear, accessible training for complex technical content. Designed and launched "
        "40+ multi-audience enablement programs for internal teams, customers, and partners, "
        "leveraging AI-assisted tools and Articulate 360. Directed curriculum modernization "
        "for Cox Communications' Residential Sales Academy, aligning learning assets to revenue "
        "and performance metrics. Seeking to apply proven enablement strategy to accelerate "
        "organizational performance and learner success."
    ),

    "skills": {
        "instructional_design": [
            "ADDIE", "Agile/SAM", "Articulate 360", "Storyline", "Rise",
            "eLearning development", "curriculum design", "LMS governance",
        ],
        "ai_tools": [
            "Microsoft Copilot", "Copilot Studio", "ChatGPT", "Gemini",
            "AI-assisted content development", "LLM prompt engineering",
        ],
        "platforms": [
            "SharePoint", "Cornerstone LMS", "Workday Learning",
            "Adobe Captivate", "Camtasia",
        ],
        "leadership": [
            "stakeholder management", "instructional design team leadership",
            "program management", "vendor coordination",
        ],
        "analysis": [
            "needs assessment", "performance consulting", "data analysis",
            "learning analytics", "Kirkpatrick evaluation",
        ],
        "tools": [
            "Microsoft Office Suite", "Microsoft Teams", "Jira", "Confluence",
            "Google Workspace",
        ],
    },

    "experience": [
        {
            "company": "Tanta Holdings LLC",
            "role": "President / Training Director - AI Enablement & Readiness",
            "duration": "Oct 2021 - Present",
            "highlights": [
                "Founded and operate Tanta Global Academy, delivering AI enablement and "
                "instructional design training programs for international learners",
                "Developed AI Enablement curriculum used across Tanta Global Assist and "
                "Tanta Visa Pathways business units",
                "Built automated content pipelines using LLMs to scale course production",
            ],
        },
        {
            "company": "Cox Communications (via Primus)",
            "role": "Senior Instructional Designer / Curriculum Development Manager",
            "duration": "Sep 2025 - Dec 2025",
            "highlights": [
                "Directed curriculum modernization for Cox's Residential Sales Academy",
                "Aligned learning assets to revenue and sales performance metrics",
                "Led a team of instructional designers through a full ADDIE cycle redesign",
            ],
        },
        {
            "company": "SAIC",
            "role": "Senior Instructional Designer",
            "duration": "Dec 2024 - Sep 2025",
            "highlights": [
                "Designed and developed multi-audience training programs for defense clients",
                "Applied Articulate 360 and AI tools to accelerate content development cycles",
            ],
        },
        {
            "company": "United States Naval Reserve",
            "role": "Administrative Services Manager - Petty Officer 1st Class",
            "duration": "Jun 2007 - Mar 2024",
            "highlights": [
                "17 years of service managing administrative programs and personnel training",
                "Led cross-functional teams in high-stakes operational environments",
            ],
        },
    ],

    "education": [
        {
            "degree": "M.Ed - Learning and Technology",
            "institution": "Western Governors University",
            "year": "Jan 2022",
        },
        {
            "degree": "B.S. - Technology and Training",
            "institution": "University of New Mexico",
            "year": "May 2012",
        },
    ],

    "certifications": [
        "Articulate 360 Certified",
    ],

    "notice_period": "2 weeks",
    "preferred_work_mode": ["remote", "hybrid"],
    "veteran": True,
}

TARGET_ROLES = [
    "AI Enablement Lead",
    "LLM Enablement Consultant",
    "Senior Instructional Designer",
    "Learning Technology Lead",
    "L&D Director",
    "AI Training Specialist",
    "Director of Learning and Development",
    "Instructional Design Manager",
]

JOB_PREFERENCES = {
    "locations": ["Remote", "Albuquerque NM", "Rio Rancho NM"],
    "experience_level": ["senior", "lead", "director"],
    "min_experience_years": 8,
    "max_experience_years": 20,
    "employment_type": ["full-time"],
    "industries": [
        "Technology",
        "Defense",
        "Healthcare",
        "Energy",
        "SaaS",
        "Government",
        "Education Technology",
        "Consulting",
    ],
    "company_size_preference": ["mid-size", "enterprise", "federal"],
    "avoid_companies": [],
    "preferred_companies": [],
}

SEARCH_CONFIG = {
    "max_jobs_per_run": 20,
    "job_boards": ["linkedin", "indeed"],
    "search_keywords": TARGET_ROLES,
    "freshness_days": 7,
}

OUTPUT_CONFIG = {
    "output_dir": "output/",
    "cv_format": "docx",
    "cover_letter_format": "docx",
    "tracker_db": "jobs_tracker.db",
}

# ---------------------------------------------------------------------------
# API keys are loaded from .env — do NOT hardcode them here.
# Required keys in .env:
#   ANTHROPIC_API_KEY
#   TAVILY_API_KEY
#   EXA_API_KEY
# Optional:
#   DATABASE_URL  (sqlite:///path/to/file.db — defaults to jobs_tracker.db)
#   CANDIDATE_EMAIL, CANDIDATE_PHONE, CANDIDATE_LINKEDIN
# ---------------------------------------------------------------------------
