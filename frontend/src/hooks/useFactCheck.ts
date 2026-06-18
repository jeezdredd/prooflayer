import { useCallback, useRef, useState } from "react";
import { factcheck } from "../api/endpoints";
import type { FactCheckResult, FactCheckStage } from "../types";

interface FactCheckState {
  isPending: boolean;
  isError: boolean;
  stage: FactCheckStage | null;
  progress: number;
  result: FactCheckResult | null;
}

const POLL_INTERVAL = 1500;
const POLL_TIMEOUT = 300_000;

export function useFactCheck() {
  const [state, setState] = useState<FactCheckState>({
    isPending: false,
    isError: false,
    stage: null,
    progress: 0,
    result: null,
  });
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stopPolling = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  };

  const submit = useCallback(async (text: string) => {
    stopPolling();
    setState({ isPending: true, isError: false, stage: "pending", progress: 0, result: null });

    let task_id: string;
    try {
      const res = await factcheck.check(text);
      task_id = res.data.task_id;
    } catch {
      setState((s) => ({ ...s, isPending: false, isError: true }));
      return;
    }

    timeoutRef.current = setTimeout(() => {
      stopPolling();
      setState((s) => ({ ...s, isPending: false, isError: true }));
    }, POLL_TIMEOUT);

    intervalRef.current = setInterval(async () => {
      try {
        const res = await factcheck.status(task_id);
        const { stage, progress, result, error } = res.data;

        if (stage === "done" && result) {
          stopPolling();
          setState({ isPending: false, isError: false, stage: "done", progress: 100, result });
        } else if (stage === "error") {
          stopPolling();
          setState({ isPending: false, isError: true, stage: "error", progress: 0, result: null });
          console.error("Factcheck task error:", error);
        } else {
          setState((s) => ({ ...s, stage: stage ?? s.stage, progress: progress ?? s.progress }));
        }
      } catch {
        stopPolling();
        setState((s) => ({ ...s, isPending: false, isError: true }));
      }
    }, POLL_INTERVAL);
  }, []);

  return { submit, ...state };
}
