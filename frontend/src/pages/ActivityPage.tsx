import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import type { ActivityEvent } from "../types";
import { formatDateTime } from "../utils";

export function ActivityPage() {
  const [events, setEvents] = useState<ActivityEvent[] | null>(null);

  useEffect(() => {
    api.listActivity(150).then(setEvents);
  }, []);

  return (
    <div>
      <h1>Activity</h1>
      <p className="subtitle">Everything that's happened, newest first.</p>
      {events === null ? (
        <p>Loading...</p>
      ) : events.length === 0 ? (
        <EmptyState title="Nothing has happened yet" />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>What happened</th>
                <th>Project</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.id}>
                  <td>{formatDateTime(event.occurred_at)}</td>
                  <td>{event.description}</td>
                  <td>
                    {event.project_id ? (
                      <Link to={`/projects/${event.project_id}`}>{event.project_name}</Link>
                    ) : (
                      "--"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
