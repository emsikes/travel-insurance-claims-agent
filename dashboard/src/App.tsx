import { useEffect, useState } from "react";
import "./styles.css";

interface Claim {
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
  status: string;
  decision?: string;
  payout?: number;
  explanation?: string;
  policy_reference?: string;
}

type View = "queue" | "claim" | "instructions";

// eslint-disable-next-line max-lines-per-function -- Dashboard is single-file for simplicity
export function App() {
  const [view, setView] = useState<View>("queue");
  const [claims, setClaims] = useState<Claim[]>([]);
  const [selectedClaim, setSelectedClaim] = useState<Claim | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void fetch("/api/claims")
      .then((res) => res.json() as Promise<Claim[]>)
      .then(setClaims)
      .finally(() => {
        setLoading(false);
      });
  }, []);

  function selectClaim(claimId: string) {
    const claim = claims.find((c) => c.claim_id === claimId);
    setSelectedClaim(claim ?? null);
    setView("claim");
  }

  function backToQueue() {
    setView("queue");
    void fetch("/api/claims")
      .then((res) => res.json() as Promise<Claim[]>)
      .then(setClaims);
  }

  const statusCounts = {
    waiting: claims.filter((c) => c.status === "waiting").length,
    in_progress: claims.filter((c) => c.status === "in_progress").length,
    waiting_for_signoff: claims.filter(
      (c) => c.status === "waiting_for_signoff",
    ).length,
    decided: claims.filter((c) => c.status === "decided").length,
  };

  return (
    <div className="app">
      <div className="header">
        <h1>UnderCover</h1>
        <nav className="nav">
          <button
            className={`nav-button ${view === "queue" ? "active" : ""}`}
            onClick={() => {
              setView("queue");
              backToQueue();
            }}
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
            <div className="summary-card status-waiting">
              <div className="summary-label">Waiting</div>
              <div className="summary-value">{statusCounts.waiting}</div>
            </div>
            <div className="summary-card status-in_progress">
              <div className="summary-label">In Progress</div>
              <div className="summary-value">{statusCounts.in_progress}</div>
            </div>
            <div className="summary-card status-waiting_for_signoff">
              <div className="summary-label">Waiting for Sign-off</div>
              <div className="summary-value">
                {statusCounts.waiting_for_signoff}
              </div>
            </div>
            <div className="summary-card status-decided">
              <div className="summary-label">Decided</div>
              <div className="summary-value">{statusCounts.decided}</div>
            </div>
          </div>

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
                    <span className={`status-badge status-${claim.status}`}>
                      {claim.status.replace(/_/g, " ")}
                    </span>
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
                      ${claim.amount_claimed.toFixed(2)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {view === "claim" && selectedClaim && (
        <div>
          <button className="back-button" onClick={backToQueue}>
            ← Back to Queue
          </button>

          <div className="panel">
            <div className="claim-header">
              <h1 className="claim-id">{selectedClaim.claim_id}</h1>
              <span className={`status-badge status-${selectedClaim.status}`}>
                {selectedClaim.status.replace(/_/g, " ")}
              </span>
            </div>

            <div className="detail-section">
              <h2>Claim Information</h2>
              <div className="detail-grid">
                <div className="detail-item">
                  <div className="detail-label">Customer ID</div>
                  <div className="detail-value mono">
                    {selectedClaim.customer_id}
                  </div>
                </div>
                <div className="detail-item">
                  <div className="detail-label">Policy ID</div>
                  <div className="detail-value mono">
                    {selectedClaim.policy_id}
                  </div>
                </div>
                <div className="detail-item">
                  <div className="detail-label">Claim Type</div>
                  <div className="detail-value">
                    {selectedClaim.claim_type.replace(/_/g, " ")}
                  </div>
                </div>
                <div className="detail-item">
                  <div className="detail-label">Submitted On</div>
                  <div className="detail-value">
                    {selectedClaim.submitted_on}
                  </div>
                </div>
                <div className="detail-item">
                  <div className="detail-label">Incident Date</div>
                  <div className="detail-value">
                    {selectedClaim.incident_date}
                  </div>
                </div>
                <div className="detail-item">
                  <div className="detail-label">Incident Location</div>
                  <div className="detail-value">
                    {selectedClaim.incident_location}
                  </div>
                </div>
              </div>

              <div className="detail-item" style={{ marginBottom: "1rem" }}>
                <div className="detail-label">Summary</div>
                <div className="detail-value">{selectedClaim.summary}</div>
              </div>

              <div className="detail-item">
                <div className="detail-label">Customer Story</div>
                <div className="detail-value">{selectedClaim.story}</div>
              </div>
            </div>

            <div className="detail-section">
              <h2>Items Claimed</h2>
              <ul className="items-list">
                {selectedClaim.items.map((item, idx) => (
                  <li key={idx}>
                    <span>
                      {item.description} ({item.category})
                    </span>
                    <span className="mono">${item.amount.toFixed(2)}</span>
                  </li>
                ))}
                <li style={{ fontWeight: 600 }}>
                  <span>Total</span>
                  <span className="mono">
                    ${selectedClaim.amount_claimed.toFixed(2)}
                  </span>
                </li>
              </ul>
            </div>

            <div className="detail-section">
              <h2>Supporting Documents</h2>
              <ul className="documents-list">
                {selectedClaim.documents.map((doc, idx) => (
                  <li key={idx} className="document-item">
                    <div className="document-name">{doc.name}</div>
                    <div className="document-content">{doc.content}</div>
                  </li>
                ))}
              </ul>
            </div>

            {selectedClaim.decision && (
              <div className="decision-panel">
                <h3>Decision: {selectedClaim.decision.toUpperCase()}</h3>
                {selectedClaim.payout !== undefined && (
                  <p
                    className="mono"
                    style={{ fontSize: "1.2rem", margin: "0.5rem 0" }}
                  >
                    Payout: ${selectedClaim.payout.toFixed(2)}
                  </p>
                )}
                {selectedClaim.explanation && (
                  <p style={{ marginTop: "1rem" }}>
                    {selectedClaim.explanation}
                  </p>
                )}
                {selectedClaim.policy_reference && (
                  <p style={{ marginTop: "0.5rem", fontSize: "0.9rem" }}>
                    Policy Reference: {selectedClaim.policy_reference}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {view === "instructions" && (
        <div className="panel">
          <h2>Agent Instructions</h2>
          <div className="instructions-panel">
            {`You are the UnderCover Agent, deciding travel insurance claims.

For each claim, follow these steps in order:
1. Set the claim's status to in_progress
2. Read the claim. It gives the policy_id (POL-...) and customer_id (CUS-...)
3. Read the policy, using the claim's policy_id
4. Read the customer's claim history, using the claim's customer_id
5. Read the policy wording
6. Analyze the claim against the policy wording
7. Make a decision: approve, decline, or refer
8. Calculate the payout if approving
9. Explain your decision in 2-3 sentences with the relevant policy section
10. Record your decision
11. Pay the claim if the payout is $1,000 or less

Never guess an id: take it from the claim. If a tool returns an error, correct it.

If the payout is over $1,000, record the decision but do not pay: it needs sign-off.`}
          </div>
        </div>
      )}
    </div>
  );
}
