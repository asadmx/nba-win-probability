import { useGameStore } from "../stores/gameStore";
import { sendToSimulator } from "../hooks/useGameSocket";

export function SimControls() {
  const status = useGameStore((s) => s.connectionStatus);
  const isPaused = useGameStore((s) => s.isPaused);
  const ticks = useGameStore((s) => s.ticks);

  if (status !== "connected" && status !== "ended") return null;

  const handlePause = () => sendToSimulator({ action: "pause" });
  const handleResume = () => sendToSimulator({ action: "resume" });
  const handleSpeed = (speed: number) => sendToSimulator({ action: "set_speed", speed });

  return (
    <div className="px-8 py-3 border-b border-[#1F2230] flex items-center gap-6 font-mono text-xs">
      <div className="flex items-center gap-2">
        {isPaused ? (
          <button
            onClick={handleResume}
            className="px-4 py-1.5 border border-prob-win text-prob-win hover:bg-prob-win hover:text-black transition-colors"
          >
            RESUME
          </button>
        ) : (
          <button
            onClick={handlePause}
            className="px-4 py-1.5 border border-[#2A2E3D] text-text-secondary hover:border-prob-neutral hover:text-prob-neutral transition-colors"
          >
            PAUSE
          </button>
        )}
      </div>

      <div className="flex items-center gap-3 text-text-secondary">
        <span>SPEED</span>
        {[1, 5, 10, 20, 50].map((s) => (
          <button
            key={s}
            onClick={() => handleSpeed(s)}
            className="px-2 py-1 border border-[#2A2E3D] hover:border-text-secondary hover:text-text-primary transition-colors"
          >
            {s}x
          </button>
        ))}
      </div>

      <div className="ml-auto text-text-secondary">
        {ticks.length} plays streamed
        {isPaused && <span className="ml-3 text-prob-neutral">PAUSED</span>}
      </div>
    </div>
  );
}