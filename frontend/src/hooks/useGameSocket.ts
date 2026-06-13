import { useEffect, useRef } from "react";
import { wsUrlForGame, wsUrlForLiveGame } from "../lib/api";
import { useGameStore } from "../stores/gameStore";
import type { WSMessage } from "../types";

let _wsSend: ((msg: object) => void) | null = null;

export function sendToSimulator(msg: object): void {
  _wsSend?.(msg);
}

export function useGameSocket(speed = 10): void {
  const selectedGameId = useGameStore((s) => s.selectedGameId);
  const liveGameId = useGameStore((s) => s.liveGameId);
  const appendTick = useGameStore((s) => s.appendTick);
  const setStatus = useGameStore((s) => s.setStatus);
  const setIsPaused = useGameStore((s) => s.setIsPaused);

  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const gameId = selectedGameId ?? liveGameId;
    if (gameId == null) return;

    wsRef.current?.close();

    const url = liveGameId
      ? wsUrlForLiveGame(liveGameId)
      : wsUrlForGame(selectedGameId!, speed);

    const ws = new WebSocket(url);
    wsRef.current = ws;

    _wsSend = (msg: object) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(msg));
      }
    };

    setStatus("connecting");
    ws.onopen = () => setStatus("connected");

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WSMessage;
        if (msg.type === "tick") appendTick(msg);
        else if (msg.type === "game_end") setStatus("ended");
        else if (msg.type === "paused") setIsPaused(true);
        else if (msg.type === "resumed") setIsPaused(false);
        else if (msg.type === "error") {
          console.error("WS error:", msg.message);
          setStatus("error");
        }
      } catch (e) {
        console.error("Failed to parse WS message:", e);
      }
    };

    ws.onerror = () => setStatus("error");

    ws.onclose = () => {
      const current = useGameStore.getState().connectionStatus;
      if (current === "connected" || current === "connecting") setStatus("ended");
    };

    return () => {
      _wsSend = null;
      ws.close();
    };
  }, [selectedGameId, liveGameId, speed, appendTick, setStatus, setIsPaused]);
}