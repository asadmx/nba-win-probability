import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type BackendStatus = "checking" | "ok" | "unreachable";

export default function App() {
  const [status, setStatus] = useState<BackendStatus>("checking");

  useEffect(() => {
    fetch(`${API_URL}/api/health`)
      .then((r) => r.json())
      .then((data) => setStatus(data.status === "ok" ? "ok" : "unreachable"))
      .catch(() => setStatus("unreachable"));
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-border-subtle px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-1.5 h-1.5 rounded-full bg-prob-win animate-pulse-slow" />
          <span className="font-mono text-[11px] tracking-[0.2em] text-text-secondary uppercase">
            NBA · Win Probability Engine
          </span>
        </div>
        <span className="font-mono text-[11px] text-text-muted tracking-wider">
          v0.1.0 · phase 1
        </span>
      </header>

      <main className="flex-1 px-6 lg:px-10 py-16 max-w-5xl mx-auto w-full">
        <div className="max-w-2xl">
          <p className="font-mono text-xs tracking-widest text-text-muted uppercase mb-4">
            Real-time analytics
          </p>
          <h1 className="text-data-lg sm:text-data-xl font-semibold tracking-tight text-text-primary leading-[1.05]">
            Live win probability for NBA games.
          </h1>
          <p className="mt-6 text-text-secondary leading-relaxed text-[15px]">
            A production-style analytics platform. Ingests play-by-play data,
            engineers game-state features, and serves predictions from a PyTorch
            model over WebSockets — all in under 50ms per update.
          </p>
        </div>

        <div className="mt-16 grid grid-cols-1 sm:grid-cols-3 gap-px bg-border-subtle border border-border-subtle">
          <StatusCell label="Backend" value={statusLabel(status)} state={status} />
          <StatusCell label="Model" value="not trained" state="pending" />
          <StatusCell label="Data" value="not ingested" state="pending" />
        </div>

        <p className="mt-8 font-mono text-[11px] text-text-muted tracking-wider">
          Phase 1: scaffolding · Phase 2: data ingestion · Phase 6: ML model · Phase 10: dashboard
        </p>
      </main>

      <footer className="border-t border-border-subtle px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <span className="font-mono text-[10px] text-text-muted tracking-widest uppercase">
            Built by Asad Malik
          </span>
          <span className="font-mono text-[10px] text-text-muted tracking-widest uppercase">
            FastAPI · PyTorch · React
          </span>
        </div>
      </footer>
    </div>
  );
}

type CellState = "ok" | "unreachable" | "checking" | "pending";

function StatusCell({
  label,
  value,
  state,
}: {
  label: string;
  value: string;
  state: CellState;
}) {
  const dotClass =
    state === "ok"
      ? "bg-prob-win"
      : state === "unreachable"
      ? "bg-prob-loss"
      : state === "checking"
      ? "bg-prob-neutral animate-pulse-slow"
      : "bg-text-muted";

  return (
    <div className="bg-bg-panel px-5 py-5">
      <div className="font-mono text-[10px] tracking-[0.2em] text-text-muted uppercase">
        {label}
      </div>
      <div className="mt-3 flex items-center gap-2.5">
        <div className={`w-1.5 h-1.5 rounded-full ${dotClass}`} />
        <span className="font-mono text-sm text-text-primary tabular">{value}</span>
      </div>
    </div>
  );
}

function statusLabel(s: BackendStatus): string {
  switch (s) {
    case "checking":
      return "connecting…";
    case "ok":
      return "online";
    case "unreachable":
      return "offline";
  }
}