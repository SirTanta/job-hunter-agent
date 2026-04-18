import { useState } from "react";
import { saveOnboarding } from "../api/client";
import type { UserProfile } from "../types/index";

interface OnboardingWizardProps {
  onComplete: () => void;
}

const EXPERIENCE_LEVELS = [
  { id: "fresher", label: "Fresher", emoji: "🎓", desc: "0–1 years" },
  { id: "junior", label: "Junior", emoji: "💼", desc: "1–3 years" },
  { id: "mid", label: "Mid", emoji: "🚀", desc: "3–6 years" },
  { id: "senior", label: "Senior", emoji: "👑", desc: "6+ years" },
];

const JOB_CATEGORIES = [
  { id: "tech", label: "Tech", emoji: "💻" },
  { id: "non-tech", label: "Non-tech", emoji: "📋" },
  { id: "bpo", label: "BPO/KPO", emoji: "🎧" },
  { id: "internship", label: "Internship", emoji: "🎯" },
  { id: "consultancy", label: "Consultancy", emoji: "🤝" },
  { id: "government", label: "Government", emoji: "🏛" },
  { id: "remote", label: "Remote", emoji: "🌍" },
];

const STEP_TITLES = ["About You", "What roles?", "Your Skills", "Preferences", "Ready!"];

function ProgressBar({ step }: { step: number }) {
  return (
    <div className="mb-8 flex items-center gap-2">
      {STEP_TITLES.map((title, i) => (
        <div key={i} className="flex flex-1 flex-col items-center gap-1">
          <div
            className={`h-1.5 w-full rounded-full transition-colors ${
              i < step ? "bg-[#7c6aff]" : i === step ? "bg-[#7c6aff]/60" : "bg-[#2a2a3a]"
            }`}
          />
          <span className={`text-[10px] ${i === step ? "text-[#7c6aff]" : "text-[#6b6b80]"}`}>
            {title}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function OnboardingWizard({ onComplete }: OnboardingWizardProps) {
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);

  // Form state
  const [name, setName] = useState("");
  const [experienceLevel, setExperienceLevel] = useState("");
  const [jobCategories, setJobCategories] = useState<string[]>([]);
  const [skills, setSkills] = useState("");
  const [resumeText, setResumeText] = useState("");
  const [locationInput, setLocationInput] = useState("Bengaluru, Remote");
  const [minFitScore, setMinFitScore] = useState(50);
  const [maxJobs, setMaxJobs] = useState(10);

  const toggleCategory = (id: string) => {
    setJobCategories((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]
    );
  };

  const canNext = () => {
    if (step === 0) return name.trim() !== "" && experienceLevel !== "";
    if (step === 1) return jobCategories.length > 0;
    if (step === 2) return skills.trim() !== "";
    return true;
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const locations = locationInput
        .split(",")
        .map((l) => l.trim())
        .filter(Boolean);
      const profile: UserProfile = {
        name,
        experience_level: experienceLevel as UserProfile["experience_level"],
        job_categories: jobCategories,
        preferred_locations: locations,
        skills,
        resume_text: resumeText || undefined,
        preferences: { min_fit_score: minFitScore, max_jobs_per_run: maxJobs },
      };
      await saveOnboarding(profile);
      onComplete();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-[#0a0a0f] p-6 font-mono text-[#e8e8f0]">
      <div className="mx-auto w-full max-w-2xl">
        {/* Brand */}
        <div className="mb-8 text-center">
          <p className="text-xl font-bold text-[#7c6aff]">Job Hunter AI</p>
          <p className="mt-1 text-xs text-[#6b6b80]">Let's set up your profile</p>
        </div>

        <ProgressBar step={step} />

        {/* Step content */}
        <div className="rounded-xl border border-[#2a2a3a] bg-[#111118] p-6">
          {step === 0 && (
            <div className="space-y-6">
              <h2 className="text-base font-bold text-[#e8e8f0]">About You</h2>
              <div>
                <label className="mb-1 block text-xs text-[#6b6b80]">Your name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Tanzil Ahmed"
                  className="w-full rounded border border-[#2a2a3a] bg-[#0a0a0f] px-3 py-2 text-sm text-[#e8e8f0] placeholder-[#6b6b80] focus:outline-none focus:ring-1 focus:ring-[#7c6aff]"
                />
              </div>
              <div>
                <label className="mb-2 block text-xs text-[#6b6b80]">Experience level</label>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {EXPERIENCE_LEVELS.map((level) => (
                    <button
                      key={level.id}
                      type="button"
                      onClick={() => setExperienceLevel(level.id)}
                      className={`flex flex-col items-center rounded-lg border p-4 transition-colors ${
                        experienceLevel === level.id
                          ? "border-[#7c6aff] bg-[#7c6aff]/10 text-[#7c6aff]"
                          : "border-[#2a2a3a] bg-[#1a1a24] text-[#6b6b80] hover:border-[#7c6aff]/50"
                      }`}
                    >
                      <span className="text-2xl">{level.emoji}</span>
                      <span className="mt-1 text-xs font-bold">{level.label}</span>
                      <span className="text-[10px]">{level.desc}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="space-y-4">
              <h2 className="text-base font-bold text-[#e8e8f0]">What roles are you looking for?</h2>
              <p className="text-xs text-[#6b6b80]">Select all that apply</p>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {JOB_CATEGORIES.map((cat) => (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => toggleCategory(cat.id)}
                    className={`flex flex-col items-center rounded-lg border p-4 transition-colors ${
                      jobCategories.includes(cat.id)
                        ? "border-[#7c6aff] bg-[#7c6aff]/10 text-[#7c6aff]"
                        : "border-[#2a2a3a] bg-[#1a1a24] text-[#6b6b80] hover:border-[#7c6aff]/50"
                    }`}
                  >
                    <span className="text-2xl">{cat.emoji}</span>
                    <span className="mt-1 text-xs font-bold">{cat.label}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-5">
              <h2 className="text-base font-bold text-[#e8e8f0]">Your Skills</h2>
              <div>
                <label className="mb-1 block text-xs text-[#6b6b80]">
                  Skills, tools, and technologies
                </label>
                <p className="mb-2 text-[10px] text-[#6b6b80]">
                  e.g. Python, Java, React, Excel, Customer Service, Data Entry
                </p>
                <textarea
                  value={skills}
                  onChange={(e) => setSkills(e.target.value)}
                  rows={4}
                  placeholder="List your skills here..."
                  className="w-full resize-none rounded border border-[#2a2a3a] bg-[#0a0a0f] px-3 py-2 text-sm text-[#e8e8f0] placeholder-[#6b6b80] focus:outline-none focus:ring-1 focus:ring-[#7c6aff]"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-[#6b6b80]">
                  Resume text{" "}
                  <span className="text-[#6b6b80]/60">(optional — paste for better AI matching)</span>
                </label>
                <textarea
                  value={resumeText}
                  onChange={(e) => setResumeText(e.target.value)}
                  rows={5}
                  placeholder="Paste your resume content here..."
                  className="w-full resize-none rounded border border-[#2a2a3a] bg-[#0a0a0f] px-3 py-2 text-sm text-[#e8e8f0] placeholder-[#6b6b80] focus:outline-none focus:ring-1 focus:ring-[#7c6aff]"
                />
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-6">
              <h2 className="text-base font-bold text-[#e8e8f0]">Preferences</h2>
              <div>
                <label className="mb-1 block text-xs text-[#6b6b80]">
                  Preferred locations{" "}
                  <span className="text-[#6b6b80]/60">(comma separated)</span>
                </label>
                <input
                  type="text"
                  value={locationInput}
                  onChange={(e) => setLocationInput(e.target.value)}
                  placeholder="e.g. Bengaluru, Remote, Mumbai"
                  className="w-full rounded border border-[#2a2a3a] bg-[#0a0a0f] px-3 py-2 text-sm text-[#e8e8f0] placeholder-[#6b6b80] focus:outline-none focus:ring-1 focus:ring-[#7c6aff]"
                />
              </div>
              <div>
                <label className="mb-2 flex items-center justify-between text-xs text-[#6b6b80]">
                  <span>Minimum fit score</span>
                  <span className="text-[#7c6aff] font-bold">{minFitScore}</span>
                </label>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={minFitScore}
                  onChange={(e) => setMinFitScore(Number(e.target.value))}
                  className="w-full accent-[#7c6aff]"
                />
                <div className="mt-1 flex justify-between text-[10px] text-[#6b6b80]">
                  <span>0 — all jobs</span>
                  <span>100 — perfect match only</span>
                </div>
              </div>
              <div>
                <label className="mb-2 flex items-center justify-between text-xs text-[#6b6b80]">
                  <span>Max jobs per run</span>
                  <span className="text-[#7c6aff] font-bold">{maxJobs}</span>
                </label>
                <input
                  type="range"
                  min={1}
                  max={50}
                  value={maxJobs}
                  onChange={(e) => setMaxJobs(Number(e.target.value))}
                  className="w-full accent-[#7c6aff]"
                />
                <div className="mt-1 flex justify-between text-[10px] text-[#6b6b80]">
                  <span>1</span>
                  <span>50</span>
                </div>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-5">
              <h2 className="text-base font-bold text-[#e8e8f0]">Ready! 🚀</h2>
              <p className="text-xs text-[#6b6b80]">Here's your profile summary:</p>
              <div className="space-y-2 rounded-lg border border-[#2a2a3a] bg-[#0a0a0f] p-4 text-xs">
                <div className="flex gap-2">
                  <span className="text-[#6b6b80]">Name:</span>
                  <span className="text-[#e8e8f0]">{name}</span>
                </div>
                <div className="flex gap-2">
                  <span className="text-[#6b6b80]">Level:</span>
                  <span className="capitalize text-[#e8e8f0]">{experienceLevel}</span>
                </div>
                <div className="flex gap-2">
                  <span className="shrink-0 text-[#6b6b80]">Roles:</span>
                  <span className="text-[#e8e8f0]">{jobCategories.join(", ")}</span>
                </div>
                <div className="flex gap-2">
                  <span className="shrink-0 text-[#6b6b80]">Skills:</span>
                  <span className="text-[#e8e8f0] line-clamp-2">{skills}</span>
                </div>
                <div className="flex gap-2">
                  <span className="shrink-0 text-[#6b6b80]">Locations:</span>
                  <span className="text-[#e8e8f0]">{locationInput}</span>
                </div>
                <div className="flex gap-2">
                  <span className="text-[#6b6b80]">Min fit score:</span>
                  <span className="text-[#7c6aff]">{minFitScore}</span>
                </div>
                <div className="flex gap-2">
                  <span className="text-[#6b6b80]">Max jobs/run:</span>
                  <span className="text-[#7c6aff]">{maxJobs}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Navigation */}
        <div className="mt-4 flex items-center justify-between">
          <button
            type="button"
            onClick={() => setStep((s) => s - 1)}
            disabled={step === 0}
            className="rounded border border-[#2a2a3a] px-5 py-2 text-xs text-[#6b6b80] hover:text-[#e8e8f0] disabled:opacity-30"
          >
            ← Back
          </button>

          {step < 4 ? (
            <button
              type="button"
              onClick={() => setStep((s) => s + 1)}
              disabled={!canNext()}
              className="rounded bg-[#7c6aff] px-5 py-2 text-xs text-white hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next →
            </button>
          ) : (
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={saving}
              className="rounded bg-[#7c6aff] px-6 py-2 text-xs text-white hover:opacity-80 disabled:opacity-40"
            >
              {saving ? "Saving..." : "Start Job Hunt 🚀"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
