import { STATUS_LABELS, type ClaimStatus } from "./api";

export function StatusBadge({ status }: Readonly<{ status: ClaimStatus }>) {
  return (
    <span className={`status-badge status-${status}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}
