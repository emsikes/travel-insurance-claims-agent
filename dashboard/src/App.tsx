import { useEffect, useState } from "react";
import {
  getJson,
  money,
  POLL_MS,
  STATUS_LABELS,
  type Claim,
  type ClaimStatus,
  type Run,
  type Step,
} from "./api";
import { ClaimSteps } from "./ClaimSteps";
import { InstructionsView } from "./InstructionsView";
import { RunPanel } from "./RunPanel";
import { ThemeToggle } from "./ThemeToggle";
import "./styles.css";

type View = "queue" | "claim" | "instructions";

const STATUSES = Object.keys(STATUS_LABELS) as ClaimStatus[];

function StatusBadge({ status }: Readonly<{ status: ClaimStatus }>) {
  return (
    <span className={`status-badge status-${status}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}

function ClaimDetail({
  claim,
  steps,
}: Readonly<{ claim: Claim; steps: Step[] }>) {
  const details: [string, string, boolean][] = [
    ["Customer ID", claim.customer_id, true],
    ["Policy ID", claim.policy_id, true],
    ["Claim Type", claim.claim_type.replace(/_/g, " "), false],
    ["Submitted On", claim.submitted_on, false],
    ["Incident Date", claim.incident_date, false],
    ["Incident Location", claim.incident_location, false],
  ];

  return (
    <div className="panel">
      <div className="claim-header">
        <h1 className="claim-id">{claim.claim_id}</h1>
        <StatusBadge status={claim.status} />
      </div>
      {claim.attempts > 0 && (
        <p className="attempts">
          Failed attempts: <span className="mono">{claim.attempts}</span>
        </p>
      )}

      <div className="detail-section">
        <h2>Claim Information</h2>
        <div className="detail-grid">
          {details.map(([label, value, mono]) => (
            <div key={label} className="detail-item">
              <div className="detail-label">{label}</div>
              <div className={`detail-value ${mono ? "mono" : ""}`}>
                {value}
              </div>
            </div>
          ))}
        </div>
        <div className="detail-item" style={{ marginBottom: "1rem" }}>
          <div className="detail-label">Summary</div>
          <div className="detail-value">{claim.summary}</div>
        </div>
        <div className="detail-item">
          <div className="detail-label">Customer Story</div>
          <div className="detail-value">{claim.story}</div>
        </div>
      </div>

      <div className="detail-section">
        <h2>Items Claimed</h2>
        <ul className="items-list">
          {claim.items.map((item, idx) => (
            <li key={idx}>
              <span>
                {item.description} ({item.category})
              </span>
              <span className="mono">{money(item.amount)}</span>
            </li>
          ))}
          <li style={{ fontWeight: 600 }}>
            <span>Total</span>
            <span className="mono">{money(claim.amount_claimed)}</span>
          </li>
        </ul>
      </div>

      <div className="detail-section">
        <h2>Supporting Documents</h2>
        <ul className="documents-list">
          {claim.documents.map((doc, idx) => (
            <li key={idx} className="document-item">
              <div className="document-name">{doc.name}</div>
              <div className="document-content">{doc.content}</div>
            </li>
          ))}
        </ul>
      </div>

      {claim.decision && (
        <div className="decision-panel detail-section">
          <h3>Decision: {claim.decision.toUpperCase()}</h3>
          {claim.payout !== null && (
            <p
              className="mono"
              style={{ fontSize: "1.2rem", margin: "0.5rem 0" }}
            >
              Payout: {money(claim.payout)}
            </p>
          )}
          {claim.status === "waiting_for_signoff" && (
            <p>
              Over the $1,000.00 approval limit: payment waits for sign-off.
            </p>
          )}
          {claim.paid_amount !== null && (
            <p className="mono">Paid: {money(claim.paid_amount)}</p>
          )}
          {claim.explanation && (
            <p style={{ marginTop: "1rem" }}>{claim.explanation}</p>
          )}
          {claim.policy_reference && (
            <p style={{ marginTop: "0.5rem", fontSize: "0.9rem" }}>
              Policy Reference: {claim.policy_reference}
            </p>
          )}
        </div>
      )}

      <ClaimSteps steps={steps} />
    </div>
  );
}

export function App() {
  const [view, setView] = useState<View>("queue");
  const [claims, setClaims] = useState<Claim[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    function refresh() {
      void getJson<Claim[]>("/api/claims")
        .then(setClaims)
        .finally(() => {
          setLoading(false);
        });
      void getJson<Run | null>("/api/runs/latest").then(setRun);
      if (selectedId) {
        void getJson<Step[]>(`/api/claims/${selectedId}/steps`).then(setSteps);
      }
    }
    refresh();
    const timer = setInterval(refresh, POLL_MS);
    return () => {
      clearInterval(timer);
    };
  }, [selectedId]);

  function selectClaim(claimId: string) {
    setSteps([]);
    setSelectedId(claimId);
    setView("claim");
  }

  function backToQueue() {
    setSelectedId(null);
    setView("queue");
  }

  const selectedClaim = claims.find((c) => c.claim_id === selectedId);

  return (
    <div className="app">
      <div className="header">
        <h1>UnderCover</h1>
        <nav className="nav">
          <button
            className={`nav-button ${view === "queue" ? "active" : ""}`}
            onClick={backToQueue}
          >
            Claims Queue
          </button>
          <button
            className={`nav-button ${view === "instructions" ? "active" : ""}`}
            onClick={() => {
              setView("instructions");
            }}
          >
            Agent Instructions
          </button>
          <ThemeToggle />
        </nav>
      </div>

      {loading && <div className="loading">Loading...</div>}

      {!loading && view === "queue" && (
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
                    selectClaim(claim.claim_id);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      selectClaim(claim.claim_id);
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
                    <div
                      className="mono"
                      style={{ fontSize: "0.85rem", marginTop: "0.5rem" }}
                    >
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
      )}

      {!loading && view === "claim" && selectedClaim && (
        <div>
          <button className="back-button" onClick={backToQueue}>
            ← Back to Queue
          </button>
          <ClaimDetail claim={selectedClaim} steps={steps} />
        </div>
      )}

      {view === "instructions" && <InstructionsView />}
    </div>
  );
}
