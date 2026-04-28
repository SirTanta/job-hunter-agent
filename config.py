# config.py — Candidate profile, job preferences, and agent configuration

CANDIDATE_PROFILE = {
    "name": "Jon Edwards, M.Ed",
    "location": "Rio Rancho, NM, USA",
    "email": "jedwards@tanta-holdings.com",
    "phone": "+1 (505) 514-2800",
    "linkedin": "linkedin.com/in/jedwar82/",
    "github": "",
    "portfolio": "https://www.tantaholdings.com/solutions/portfolio",

    "summary": (
        "Senior Instructional Designer and AI Enablement specialist with 15+ years "
        "building high-impact learning programs across federal, defense, healthcare, "
        "energy, and enterprise sectors. Developed 3,000+ hours of eLearning using "
        "Articulate 360, Adobe Captivate, and custom SCORM platforms. Led curriculum "
        "modernization for Cox Communications, FAA modernization training at SAIC, and "
        "DoE compliance eLearning adopted as a national training standard. Built and "
        "launched TGA Academy — a full-stack LMS (Next.js, Supabase, SCORM 1.2) with "
        "scenario-based capstone simulations. Proven at translating complex technical "
        "and AI content into measurable learning outcomes. US Navy veteran, 17 years."
    ),

    "skills": {
        "instructional_design": [
            "ADDIE", "Agile/SAM", "Successive Approximation Model",
            "Kirkpatrick Four Levels", "Human Performance Improvement (HPI)",
            "needs analysis", "curriculum design", "storyboarding",
            "learning objectives (Bloom's)", "scenario-based design",
            "assessment design", "performance consulting",
        ],
        "elearning_development": [
            "Articulate Storyline 360", "Articulate Rise 360",
            "Adobe Captivate", "SCORM 1.2", "xAPI/Tin Can",
            "508/WCAG 2.0 accessibility", "branching scenarios",
            "simulation-based training", "software tutorials",
            "facilitator guides", "job aids", "OpenEdX/EdX Studio",
        ],
        "ai_tools": [
            "Microsoft Copilot", "Copilot Studio", "ChatGPT/GPT-4",
            "Google Gemini", "Claude (Anthropic)", "MindSmith AI authoring",
            "Synthesia AI video", "AI-assisted content development",
            "LLM prompt engineering", "AI enablement curriculum design",
        ],
        "learning_technology": [
            "LMS administration", "TGA Academy (custom LMS build)",
            "LearnWorlds", "SumTotal", "Cornerstone LMS", "Workday Learning",
            "SharePoint", "SCORM player development", "learning analytics",
        ],
        "design_tools": [
            "Figma", "Adobe Creative Cloud", "Photoshop", "InDesign",
            "Premiere Pro", "Camtasia", "Adobe Captivate",
        ],
        "leadership": [
            "stakeholder management", "SME collaboration",
            "instructional design team leadership", "program management",
            "vendor coordination", "content governance",
        ],
        "technical": [
            "Next.js", "React", "Supabase", "PostgreSQL",
            "GitHub Actions", "Microsoft Office Suite",
            "Jira", "Confluence", "Google Workspace",
        ],
    },

    "experience": [
        {
            "company": "Tanta Holdings LLC",
            "role": "President / Training Director - AI Enablement & Instructional Design",
            "duration": "Oct 2021 - Present",
            "highlights": [
                "Built TGA Academy from scratch — full-stack LMS (Next.js, Supabase, SCORM 1.2) "
                "with scenario-based capstone simulations, rubric grading, and credential registry",
                "Designed 40+ enablement programs using ADDIE and Agile methodologies for "
                "international learners across sales, customer service, and remote work domains",
                "Developed AI enablement curriculum for Microsoft Copilot, ChatGPT, and Gemini "
                "adoption, boosting learner AI tool adoption by 20%",
                "Created browser-based capstone simulations replicating Excel, PowerPoint, Word, "
                "CRM, and Kanban workflows for realistic performance assessment",
            ],
        },
        {
            "company": "Cox Communications (via Primus Software Corporation)",
            "role": "Senior Instructional Designer / Curriculum Development Manager",
            "duration": "Sep 2025 - Dec 2025",
            "highlights": [
                "Directed curriculum modernization for Cox's Residential Sales Academy, "
                "aligning 40+ learning assets to revenue and performance metrics",
                "Led multi-team SME collaboration using Figma to prototype and validate "
                "learning experiences before development, cutting revision cycles by 30%",
                "Produced modular SCORM courseware for sales processes, systems training, "
                "and customer experience using Articulate Storyline 360",
            ],
        },
        {
            "company": "SAIC",
            "role": "Senior Instructional Designer",
            "duration": "Dec 2024 - Sep 2025",
            "highlights": [
                "Led federal learning program for FAA systems modernization — translated "
                "complex ATC technical systems into SCORM-compliant training modules enabling "
                "pilots and staff to meet compliance standards on schedule",
                "Collaborated with engineering SMEs to conduct task analysis and convert "
                "technical requirements into structured learning objectives at Bloom's Apply level",
                "Implemented content governance, version control, and QA evaluation framework "
                "across 15+ training assets",
            ],
        },
        {
            "company": "United States Naval Reserve",
            "role": "Administrative Services Manager - Petty Officer 1st Class",
            "duration": "Jun 2007 - Mar 2024",
            "highlights": [
                "Led training enablement and readiness programs for 200+ personnel — "
                "designed curriculum, built tracking systems, ensured compliance",
                "Created Navy Evaluations tutorial adopted fleet-wide, achieving 16,000+ views",
                "Managed documentation governance using SharePoint, driving zero audit findings",
            ],
        },
    ],

    "additional_experience": [
        "Department of Energy — Senior ISD/eLearning Developer: 3,000+ hours compliance eLearning; "
        "508/WCAG accessibility guidelines adopted as DOE National Training Center standard",
        "Southern California Edison — Senior ISD: 15+ facilitator and student guides for substation "
        "electrician apprenticeship programs; complex utility/engineering content",
        "Applied Materials — Senior ISD: managed 11 concurrent eLearning projects; technical product content",
        "Presbyterian Healthcare Services — Epic ISD/Credentialed Trainer: "
        "blended learning for Epic EHR clinical workflows",
        "Northrop Grumman — ISD: 12 storyboards, 170+ pages, 40+ quick reference guides",
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

    "publications": [
        "The Documentation Standard: The Instructional Designer's Edge (Kindle, 2025)",
        "The American Standard (Kindle, 2026)",
    ],

    "notice_period": "2 weeks",
    "preferred_work_mode": ["remote", "hybrid"],
    "veteran": True,
}

TARGET_ROLES = [
    # AI / Enablement track
    "AI Enablement Lead",
    "AI Training Specialist",
    "LLM Enablement Consultant",
    "Learning Technology Lead",
    # Instructional Design track
    "Senior Instructional Designer",
    "Instructional Design Manager",
    "Senior eLearning Developer",
    "Senior Learning Experience Designer",
    "Instructional Systems Designer",
    "eLearning Developer",
    "Curriculum Developer",
    # Leadership track
    "Director of Learning and Development",
    "L&D Director",
    "Director of Instructional Design",
    "Head of Learning",
]

JOB_PREFERENCES = {
    "locations": ["Remote", "Albuquerque NM", "Rio Rancho NM"],
    "experience_level": ["senior", "lead", "director", "manager"],
    "min_experience_years": 8,
    "max_experience_years": 20,
    "employment_type": ["full-time"],
    "industries": [
        "Technology",
        "Defense",
        "Healthcare",
        "Energy / Utilities",
        "SaaS",
        "Federal Government",
        "Education Technology",
        "Consulting",
        "Finance",
        "Telecommunications",
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
    "resume_format": "docx",
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
