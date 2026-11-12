import {
  money,
  STATUS_LABELS,
  type Claim,
  type ClaimStatus,
  type Run,
} from "./api";
import { RunPanel } from "./RunPanel";
import { StatusBadge } from "./StatusBadge";

const STATUSES = Object.keys(STATUS_LABELS) as ClaimStatus[];

export function QueueView({
  claims,
  run,
  onSelect,
}: Readonly<{
  claims: Claim[];
  run: Run | null;
  onSelect: (claimId: string) => void;
}>) {
  return (
    <>
      <div className="summary-dashboard">
        <div className="summary-card">
          <div className="summary-label">Total Claims</div>
          <div className="summary-value">{claims.length}</div>
        </div>
        {STATUSES.map((status) => (
          <div key={status} className={`summary-card status-${status}`}>
            <div className="summary-label">{STATUS_LABELS[status]}</div>
            <div className="summary-value">
              {claims.filter((c) => c.status === status).length}
            </div>
          </div>
        ))}
      </div>

      {run && <RunPanel run={run} />}

      <div className="panel">
        <h2>Claims Queue ({claims.length})</h2>
        <div className="claims-grid">
          {claims.map((claim) => (
            <div
              key={claim.claim_id}
              className="claim-card"
              onClick={() => {
                onSelect(claim.claim_id);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  onSelect(claim.claim_id);
                }
              }}
              role="button"
              tabIndex={0}
            >
              <div className="claim-header">
                <span className="claim-id">{claim.claim_id}</span>
                <StatusBadge status={claim.status} />
              </div>
              <div className="claim-details">
                <div>{claim.summary}</div>
                <div className="mono claim-meta">
                  {claim.incident_location} • {claim.incident_date}
                </div>
                <div className="claim-amount mono">
                  {money(claim.amount_claimed)}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
