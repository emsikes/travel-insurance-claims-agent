import { ThemeToggle } from "./ThemeToggle";

export type View = "queue" | "claim" | "instructions";

export function Header({
  view,
  showQueue,
  showInstructions,
}: Readonly<{
  view: View;
  showQueue: () => void;
  showInstructions: () => void;
}>) {
  return (
    <div className="header">
      <h1>UnderCover</h1>
      <nav className="nav">
        <button
          className={`nav-button ${view === "queue" ? "active" : ""}`}
          onClick={showQueue}
        >
          Claims Queue
        </button>
        <button
          className={`nav-button ${view === "instructions" ? "active" : ""}`}
          onClick={showInstructions}
        >
          Agent Instructions
        </button>
        <ThemeToggle />
      </nav>
    </div>
  );
}
