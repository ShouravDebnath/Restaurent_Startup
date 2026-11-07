import type { Me } from "../settings/types";
export type { Me };
export type State = "UNKNOWN" | "AVAILABLE" | "OCCUPIED" | "RESET_PENDING" | "CLEANING" | "OUT_OF_SERVICE";
export type Table = {
  id: string; label: string; seats: number | null; current_state: State; state_since: string;
  operational_revision: number; state_source: string; occupied_since: string | null;
  source_status: string; observation: string; observed_at: string | null;
};
export type Task = {
  id: string; table_id: string; status: string; created_at: string;
  acknowledged_at: string | null; started_at: string | null;
};
export type Activity = {
  id: string; table_id: string; revision: number; event_type: string; source: string;
  occurred_at: string; previous_state: State; new_state: State;
};
export type Dashboard = {
  demo: boolean; simulation_controls: boolean; role: string; server_time: string; cursor: string;
  location: { id: string; name: string; time_zone: string };
  tables: Table[]; tasks: Task[]; tables_truncated: boolean; tasks_truncated: boolean;
};
export const labels: Record<State, string> = {
  AVAILABLE: "Available", OCCUPIED: "Occupied", RESET_PENDING: "Reset pending",
  CLEANING: "Cleaning", UNKNOWN: "Unknown", OUT_OF_SERVICE: "Out of service",
};
export const symbols: Record<State, string> = {
  AVAILABLE: "✓", OCCUPIED: "●", RESET_PENDING: "!", CLEANING: "↻", UNKNOWN: "?", OUT_OF_SERVICE: "×",
};
export function elapsed(since: string, now: number) {
  if (!now) return "—";
  const seconds = Math.max(0, Math.floor((now - Date.parse(since)) / 1000));
  const hours = Math.floor(seconds / 3600);
  return `${hours ? `${hours}:` : ""}${String(Math.floor(seconds / 60) % 60).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}
