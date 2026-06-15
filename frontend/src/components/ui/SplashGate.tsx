import { useEffect, useState, type ReactNode } from "react";
import Loader from "./Loader";

const SESSION_KEY = "pl_splash_shown";
const MIN_SPLASH_MS = 2000;

export default function SplashGate({ children }: { children: ReactNode }) {
  const alreadyShown = typeof sessionStorage !== "undefined" && !!sessionStorage.getItem(SESSION_KEY);
  const [ready, setReady] = useState(alreadyShown);

  useEffect(() => {
    if (alreadyShown) return;
    const t = setTimeout(() => {
      sessionStorage.setItem(SESSION_KEY, "1");
      setReady(true);
    }, MIN_SPLASH_MS);
    return () => clearTimeout(t);
  }, [alreadyShown]);

  if (!ready) {
    return (
      <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-ink-950">
        <Loader />
      </div>
    );
  }

  return <>{children}</>;
}
