import { useEffect } from "react";
import client, { setAccessToken } from "../api/client";
import { auth } from "../api/endpoints";
import { useAuthStore } from "../stores/authStore";

const MIN_GAP_MS = 10_000;
let lastRun = 0;
let running: Promise<void> | null = null;

async function reconcile(): Promise<void> {
  const store = useAuthStore.getState();
  const { data } = await client.get<{ user_id: number | null }>("/auth/session/");
  const sessionUser = data.user_id;
  if (sessionUser == null) {
    if (store.isAuthenticated) store.logout();
    return;
  }
  if (store.isAuthenticated && store.user?.id === sessionUser) return;
  const refreshed = await auth.refresh();
  setAccessToken(refreshed.data.access);
  store.setAccess(refreshed.data.access);
  const me = await auth.me();
  store.setUser(me.data);
}

export function syncSession(force = false): Promise<void> {
  const now = Date.now();
  if (running) return running;
  if (!force && now - lastRun < MIN_GAP_MS) return Promise.resolve();
  lastRun = now;
  running = reconcile()
    .catch(() => undefined)
    .finally(() => {
      running = null;
    });
  return running;
}

export function useSessionSync(): void {
  useEffect(() => {
    syncSession(true);
    const onVisible = () => {
      if (document.visibilityState === "visible") syncSession();
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);
    return () => {
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
    };
  }, []);
}
