import type { Step } from "./api";

const KIND_LABELS: Record<Step["kind"], string> = {
  tool_call: "Tool",
  section_read: "Read",
  result: "Result",
  error: "Error",
};

function time(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", { hour12: false });
}

export function ClaimSteps({ steps }: Readonly<{ steps: Step[] }>) {
  const sectionsRead = [
    ...new Set(
      steps.filter((s) => s.kind === "section_read").map((s) => s.text),
    ),
  ];

  return (
    <>
      <div className="detail-section">
        <h2>Sections Read</h2>
        {sectionsRead.length === 0 ? (
          <p className="muted">The agent has not read any sections yet.</p>
        ) : (
          <ul className="sections-list">
            {sectionsRead.map((section) => (
              <li key={section}>{section}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="detail-section">
        <h2>Agent Steps</h2>
        {steps.length === 0 ? (
          <p className="muted">The agent has not worked this claim yet.</p>
        ) : (
          <ol className="steps-list">
            {steps.map((step, idx) => (
              <li key={idx} className={`step step-${step.kind}`}>
                <span className="mono step-time">{time(step.created_at)}</span>
                <span className="step-kind">
                  {KIND_LABELS[step.kind]}
                  {step.attempt > 1 && ` (attempt ${String(step.attempt)})`}
                </span>
                <span className="step-text">{step.text}</span>
              </li>
            ))}
          </ol>
        )}
      </div>
    </>
  );
}
