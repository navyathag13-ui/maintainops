import { useEffect, useState } from "react";
import { api } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { NewProjectForm } from "../components/NewProjectForm";
import { ProjectCard } from "../components/ProjectCard";
import { Toast } from "../components/Toast";
import type { ProjectSummary } from "../types";

export function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  function refresh() {
    return api.listProjects().then(setProjects);
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <h1>Projects</h1>
      <p className="subtitle">Every job site, who's running it, and what's deployed there.</p>

      {!showForm && <button onClick={() => setShowForm(true)}>+ New Project</button>}

      {showForm && (
        <NewProjectForm
          onCancel={() => setShowForm(false)}
          onSuccess={(project) => {
            setShowForm(false);
            refresh();
            setToast(`${project.name} created.`);
          }}
        />
      )}

      <div style={{ marginTop: "1.25rem" }}>
        {projects === null ? (
          <p>Loading...</p>
        ) : projects.length === 0 ? (
          <EmptyState title="No projects yet" description="Add the first project above." />
        ) : (
          <div className="project-grid">
            {projects.map((p) => (
              <ProjectCard key={p.id} project={p} />
            ))}
          </div>
        )}
      </div>

      {toast && <Toast message={toast} onDismiss={() => setToast(null)} />}
    </div>
  );
}
