import { useEffect, useState } from "react";
import { fetchInstructions, type Instructions } from "./api";

export function InstructionsView() {
  const [instructions, setInstructions] = useState<Instructions | null>(null);

  useEffect(() => {
    void fetchInstructions().then(setInstructions);
  }, []);

  if (!instructions) {
    return <div className="loading">Loading...</div>;
  }

  return (
    <>
      <section className="panel" aria-label="Running the queue">
        <h2>Running the Queue</h2>
        <div className="instructions-panel">{instructions.queue}</div>
      </section>
      <section className="panel" aria-label="Working a claim">
        <h2>Working a Claim</h2>
        <div className="instructions-panel">{instructions.claim}</div>
      </section>
    </>
  );
}
