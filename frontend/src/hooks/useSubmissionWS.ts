import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getAccessToken } from "../api/client";

const VITE_API_URL = import.meta.env.VITE_API_URL || "/api/v1";

function getWsUrl(submissionId: string, token: string): string {
  const base = VITE_API_URL.replace(/\/api\/v1\/?$/, "");
  const proto = base.startsWith("https") ? "wss" : "ws";
  const host = base.replace(/^https?:\/\//, "");
  return `${proto}://${host}/ws/submissions/${submissionId}/?token=${encodeURIComponent(token)}`;
}

const BACKOFF = [1000, 2000, 5000, 10000];

export function useSubmissionWS(submissionId: string | null | undefined) {
  const queryClient = useQueryClient();
  const [connected, setConnected] = useState(false);
  const [runningAnalyzers, setRunningAnalyzers] = useState<Set<string>>(new Set());
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stoppedRef = useRef(false);

  useEffect(() => {
    if (!submissionId) return;

    stoppedRef.current = false;
    retryRef.current = 0;
    setRunningAnalyzers(new Set());

    function connect() {
      if (stoppedRef.current) return;
      const token = getAccessToken();
      if (!token) return;

      const ws = new WebSocket(getWsUrl(submissionId!, token));
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        retryRef.current = 0;
      };

      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data as string);

          if (data.event === "analyzer_start" && data.analyzer) {
            setRunningAnalyzers((prev) => {
              const next = new Set(prev);
              next.add(data.analyzer);
              return next;
            });
            return;
          }

          if (data.event === "analyzer_done" && data.analyzer) {
            setRunningAnalyzers((prev) => {
              const next = new Set(prev);
              next.delete(data.analyzer);
              return next;
            });
            return;
          }

          queryClient.setQueryData(["submission", submissionId], (old: Record<string, unknown> | undefined) => {
            if (!old) return old;
            return {
              ...old,
              ...(data.status_message !== undefined && { status_message: data.status_message }),
              ...(data.status !== undefined && { status: data.status }),
              ...(data.final_score !== undefined && { final_score: data.final_score }),
              ...(data.final_verdict !== undefined && { final_verdict: data.final_verdict }),
            };
          });

          if (data.status === "completed" || data.status === "failed") {
            stoppedRef.current = true;
            setRunningAnalyzers(new Set());
            ws.close();
            queryClient.invalidateQueries({ queryKey: ["submission", submissionId] });
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        setConnected(false);
        if (!stoppedRef.current) {
          const delay = BACKOFF[Math.min(retryRef.current, BACKOFF.length - 1)];
          retryRef.current += 1;
          timerRef.current = setTimeout(connect, delay);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      stoppedRef.current = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      wsRef.current?.close();
      setConnected(false);
      setRunningAnalyzers(new Set());
    };
  }, [submissionId, queryClient]);

  return { connected, runningAnalyzers };
}
