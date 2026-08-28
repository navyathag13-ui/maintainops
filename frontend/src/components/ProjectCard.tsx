import { Link } from "react-router-dom";
import type { ProjectSummary } from "../types";
import { ProjectStatusBadge } from "./ProjectStatusBadge";

export function ProjectCard({ project }: { project: ProjectSummary }) {
  const notices: string[] = [];
  if (project.maintenance_warning_count > 0) {
    notices.push(
      `${project.maintenance_warning_count} maintenance warning${project.maintenance_warning_count === 1 ? "" : "s"}`
    );
  }
  if (project.due_back_soon_count > 0) {
    notices.push(
      `${project.due_back_soon_count} item${project.due_back_soon_count === 1 ? "" : "s"} due back soon`
    );
  }

  return (
    <Link to={`/projects/${project.id}`} className="project-card">
      <div className="project-card-header">
        <strong>{project.name}</strong>
        <ProjectStatusBadge status={project.status} />
      </div>
      <div className="project-card-manager">Manager: {project.manager_name ?? "Unassigned"}</div>
      <div className="project-card-stats">
        <span>{project.equipment_count} Equipment</span>
        <span>{project.parts_used_count} Parts Used</span>
        <span>{project.worker_count} Workers</span>
      </div>
      <div className={`project-card-notice ${notices.length > 0 ? "project-card-notice-warning" : ""}`}>
        {notices.length > 0 ? notices.join(" · ") : "All good"}
      </div>
    </Link>
  );
}
