import { useEffect, useState } from "react";
import { auth } from "../api/endpoints";
import { setAccessToken } from "../api/client";
import { useAuthStore } from "../stores/authStore";

let attempt: Promise<void> | null = null;

function signInFromCookie(): Promise<void> {
  attempt ??= auth
    .refresh()
    .then(async (res) => {
      setAccessToken(res.data.access);
      const me = await auth.me();
      const store = useAuthStore.getState();
      store.setAccess(res.data.access);
      store.setUser(me.data);
    })
    .catch(() => setAccessToken(null));
  return attempt;
}

export function useSilentSignIn(): boolean {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    useAuthStore.getState().hydrate();
    if (useAuthStore.getState().isAuthenticated) {
      setReady(true);
      return;
    }
    let cancelled = false;
    signInFromCookie().finally(() => {
      if (!cancelled) setReady(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return ready;
}
