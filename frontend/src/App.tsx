import { useCallback, useEffect, useState } from "react";
import { fetchOnboarding, fetchRunStatus } from "./api/client";
import ApplicationsPage from "./components/ApplicationsPage";
import DashboardPage from "./components/DashboardPage";
import FilesPage from "./components/FilesPage";
import JobsPage from "./components/JobsPage";
import OnboardingWizard from "./components/OnboardingWizard";
import RunAgentPage from "./components/RunAgentPage";
import SettingsPage from "./components/SettingsPage";
import Sidebar from "./components/Sidebar";
import SkillGapPage from "./components/SkillGapPage";

type Page = "setup" | "dashboard" | "run-agent" | "jobs" | "applications" | "files" | "skill-gap" | "settings";

export default function App() {
  const [currentPage, setCurrentPage] = useState<Page>("dashboard");
  const [agentStatus, setAgentStatus] = useState("idle");

  // Check onboarding on mount — redirect to setup if no profile
  useEffect(() => {
    const check = async () => {
      try {
        const profile = await fetchOnboarding();
        if (!profile) setCurrentPage("setup");
      } catch {
        // backend unreachable — stay on default page
      }
    };
    void check();
  }, []);

  // Poll run status every 5 s
  useEffect(() => {
    const poll = async () => {
      try {
        const data = await fetchRunStatus();
        setAgentStatus(data.status);
      } catch {
        // backend not reachable — keep last known status
      }
    };
    void poll();
    const id = setInterval(() => { void poll(); }, 5000);
    return () => clearInterval(id);
  }, []);

  const handleStatusChange = useCallback((status: string) => setAgentStatus(status), []);

  const renderPage = () => {
    switch (currentPage) {
      case "setup":         return <OnboardingWizard onComplete={() => setCurrentPage("run-agent")} />;
      case "dashboard":     return <DashboardPage />;
      case "run-agent":     return <RunAgentPage agentStatus={agentStatus} onStatusChange={handleStatusChange} />;
      case "jobs":          return <JobsPage />;
      case "applications":  return <ApplicationsPage />;
      case "files":         return <FilesPage />;
      case "skill-gap":     return <SkillGapPage />;
      case "settings":      return <SettingsPage />;
    }
  };

  if (currentPage === "setup") {
    return <OnboardingWizard onComplete={() => setCurrentPage("run-agent")} />;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#0a0a0f] font-mono text-[#e8e8f0]">
      <Sidebar
        activePage={currentPage}
        onNavigate={(page) => setCurrentPage(page)}
        agentStatus={agentStatus}
      />
      <main className="flex-1 overflow-y-auto">
        {renderPage()}
      </main>
    </div>
  );
}
