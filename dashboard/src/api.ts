export type ClaimStatus =
  | "waiting"
  | "in_progress"
  | "waiting_for_signoff"
  | "decided"
  | "needs_handler";

export interface Claim {
  claim_id: string;
  customer_id: string;
  policy_id: string;
  claim_type: string;
  submitted_on: string;
  incident_date: string;
  incident_location: string;
  summary: string;
  story: string;
  items: { description: string; category: string; amount: number }[];
  amount_claimed: number;
  documents: { name: string; type: string; content: string }[];
  status: ClaimStatus;
  decision: string | null;
  payout: number | null;
  explanation: string | null;
  policy_reference: string | null;
  attempts: number;
  paid_amount: number | null;
}

export type TodoStatus = "to_do" | "in_progress" | "done" | "left_for_handler";

export interface Todo {
  claim_id: string;
  content: string;
  status: TodoStatus;
}

export interface Run {
  run_id: string;
  cap: number;
  status: "running" | "finished";
  todos: Todo[];
  summary: string | null;
  started_at: string;
}

export interface Step {
  attempt: number;
  kind: "tool_call" | "section_read" | "result" | "error";
  text: string;
  created_at: string;
}

export interface Instructions {
  queue: string;
  claim: string;
}

export const STATUS_LABELS: Record<ClaimStatus, string> = {
  waiting: "Waiting",
  in_progress: "In Progress",
  waiting_for_signoff: "Waiting for Sign-off",
  decided: "Decided",
  needs_handler: "Left for a Handler",
};

export const TODO_LABELS: Record<TodoStatus, string> = {
  to_do: "To do",
  in_progress: "In progress",
  done: "Done",
  left_for_handler: "Left for a handler",
};

export const TODO_CLASSES: Record<TodoStatus, ClaimStatus> = {
  to_do: "waiting",
  in_progress: "in_progress",
  done: "decided",
  left_for_handler: "needs_handler",
};

export const POLL_MS = 2000;

export async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  return (await response.json()) as T;
}

export function money(amount: number): string {
  return `$${amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
