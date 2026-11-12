import { money, type Claim, type Step } from "./api";
import { ClaimSteps } from "./ClaimSteps";
import { StatusBadge } from "./StatusBadge";

function Decision({
  claim,
  approvalLimit,
}: Readonly<{ claim: Claim; approvalLimit: number | null }>) {
  const limit = approvalLimit === null ? "" : `${money(approvalLimit)} `;
  return (
    <div className="decision-panel detail-section">
      <h3>Decision: {claim.decision?.toUpperCase()}</h3>
      {claim.payout !== null && (
        <p className="mono payout">Payout: {money(claim.payout)}</p>
      )}
      {claim.status === "waiting_for_signoff" && (
        <p>Over the {limit}approval limit: payment waits for sign-off.</p>
      )}
      {claim.paid_amount !== null && (
        <p className="mono">Paid: {money(claim.paid_amount)}</p>
      )}
      {claim.explanation && <p className="explanation">{claim.explanation}</p>}
      {claim.policy_reference && (
        <p className="policy-reference">
          Policy Reference: {claim.policy_reference}
        </p>
      )}
    </div>
  );
}

export function ClaimDetail({
  claim,
  steps,
  approvalLimit,
}: Readonly<{ claim: Claim; steps: Step[]; approvalLimit: number | null }>) {
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
        <div className="detail-item spaced">
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
          <li className="items-total">
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
        <Decision claim={claim} approvalLimit={approvalLimit} />
      )}

      <ClaimSteps steps={steps} />
    </div>
  );
}
