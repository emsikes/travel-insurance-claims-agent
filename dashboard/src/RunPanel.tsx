import { TODO_CLASSES, TODO_LABELS, type Run } from "./api";

export function RunPanel({ run }: Readonly<{ run: Run }>) {
  const done = run.todos.filter(
    (todo) => todo.status === "done" || todo.status === "left_for_handler",
  ).length;

  return (
    <section className="panel run-panel" aria-label="Current run">
      <div className="claim-header">
        <h2>
          {run.status === "running"
            ? "Agent run in progress"
            : "Last agent run"}
        </h2>
        <span className="mono run-progress">
          {done} of {run.todos.length} done
        </span>
      </div>
      <p className="run-meta">
        <span className="mono">{run.run_id}</span> · capped at{" "}
        <span className="mono">{run.cap}</span> claims
      </p>
      {run.todos.length === 0 ? (
        <p className="muted">The agent is planning its work.</p>
      ) : (
        <ol className="todo-list">
          {run.todos.map((todo, idx) => (
            <li key={`${todo.claim_id}-${String(idx)}`} className="todo-item">
              <span
                className={`status-badge status-${TODO_CLASSES[todo.status]}`}
              >
                {TODO_LABELS[todo.status]}
              </span>
              <span>{todo.content}</span>
            </li>
          ))}
        </ol>
      )}
      {run.summary && (
        <div className="run-summary">
          <h3>Summary</h3>
          <p>{run.summary}</p>
        </div>
      )}
    </section>
  );
}
