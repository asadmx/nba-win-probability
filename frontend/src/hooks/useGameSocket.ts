import { useEffect, useRef } from "react";
import { wsUrlForGame } from "../lib/api";
import { useGameStore } from "../stores/gameStore";
import type { WSMessage } from "../types";

/**
 * Opens a WebSocket to the simulator for the currently selected game.
 *
 * Lifecycle:
 *   - When `selectedGameId` changes, close the previous socket and open a new one.
 *   - Tick messages are pushed into the Zustand store.
 *   - On game_end, status flips to "ended" but ticks remain visible.
 *   - On unmount, close cleanly.
 */
export function useGameSocket(speed = 10): void {
  const selectedGameId = useGameStore((s) => s.selectedGameId);
  const appendTick = useGameStore((s) => s.appendTick);
  const setStatus = useGameStore((s) => s.setStatus);

  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (selectedGameId == null) return;

    wsRef.current?.close();

    const url = wsUrlForGame(selectedGameId, speed);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    setStatus("connecting");

    ws.onopen = () => {
      setStatus("connected");
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WSMessage;
        if (msg.type === "tick") {
          appendTick(msg);
        } else if (msg.type === "game_end") {
          setStatus("ended");
        } else if (msg.type === "error") {
          console.error("WS error message:", msg.message);
          setStatus("error");
        }
      } catch (e) {
        console.error("Failed to parse WS message:", e);
      }
    };

    ws.onerror = (e) => {
      console.error("WS error:", e);
      setStatus("error");
    };

    ws.onclose = () => {
      const currentStatus = useGameStore.getState().connectionStatus;
      if (currentStatus === "connected" || currentStatus === "connecting") {
        setStatus("ended");
      }
    };

    return () => {
      ws.close();
    };
  }, [selectedGameId, speed, appendTick, setStatus]);
}