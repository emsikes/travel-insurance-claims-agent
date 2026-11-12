import { useEffect, useState } from "react";
import {
  fetchClaims,
  fetchLatestRun,
  fetchSettings,
  fetchSteps,
  POLL_MS,
  type Claim,
  type Run,
  type Step,
} from "./api";
import { ClaimDetail } from "./ClaimDetail";
import { Header, type View } from "./Header";
import { InstructionsView } from "./InstructionsView";
import { QueueView } from "./QueueView";
import "./styles.css";

function every(ms: number, task: () => void): () => void {
  task();
  const timer = setInterval(task, ms);
  return () => {
    clearInterval(timer);
  };
}

export function App() {
  const [view, setView] = useState<View>("queue");
  const [claims, setClaims] = useState<Claim[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [approvalLimit, setApprovalLimit] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  const onInstructions = view === "instructions";
  const runId = run?.run_id;
  const running = run?.status === "running";

  useEffect(() => {
    void fetchSettings().then((settings) => {
      setApprovalLimit(settings.payout_approval_limit);
    });
  }, []);

  // The latest run is small, so it is polled to spot a run starting.
  useEffect(() => {
    if (onInstructions) return;
    return every(POLL_MS, () => {
      void fetchLatestRun().then(setRun);
    });
  }, [onInstructions]);

  // Claims and steps are fetched when a view opens or a run starts or ends,
  // and polled only while a run is in progress.
  useEffect(() => {
    if (onInstructions) return;
    function refresh() {
      void fetchClaims()
        .then(setClaims)
        .finally(() => {
          setLoading(false);
        });
      if (selectedId) void fetchSteps(selectedId).then(setSteps);
    }
    if (!running) {
      refresh();
      return;
    }
    return every(POLL_MS, refresh);
  }, [onInstructions, selectedId, runId, running]);

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
      <Header
        view={view}
        showQueue={backToQueue}
        showInstructions={() => {
          setView("instructions");
        }}
      />

      {loading && !onInstructions && <div className="loading">Loading...</div>}

      {!loading && view === "queue" && (
        <QueueView claims={claims} run={run} onSelect={selectClaim} />
      )}

      {!loading && view === "claim" && selectedClaim && (
        <div>
          <button className="back-button" onClick={backToQueue}>
            ← Back to Queue
          </button>
          <ClaimDetail
            claim={selectedClaim}
            steps={steps}
            approvalLimit={approvalLimit}
          />
        </div>
      )}

      {onInstructions && <InstructionsView />}
    </div>
  );
}
