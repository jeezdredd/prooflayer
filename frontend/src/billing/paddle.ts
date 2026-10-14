export interface PaddleConfig {
  environment: "sandbox" | "live";
  client_token: string;
}

interface PaddleEvent {
  name?: string;
}

interface PaddleGlobal {
  Environment: { set: (env: string) => void };
  Initialize: (options: { token: string; eventCallback?: (event: PaddleEvent) => void }) => void;
  Checkout: {
    open: (options: { transactionId: string; settings?: Record<string, unknown> }) => void;
  };
}

declare global {
  interface Window {
    Paddle?: PaddleGlobal;
  }
}

const SCRIPT_URL = "https://cdn.paddle.com/paddle/v2/paddle.js";
let ready: Promise<PaddleGlobal> | null = null;
let onCompleted: (() => void) | null = null;

function loadScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.Paddle) return resolve();
    const script = document.createElement("script");
    script.src = SCRIPT_URL;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("paddle.js failed to load"));
    document.head.appendChild(script);
  });
}

export function initPaddle(config: PaddleConfig): Promise<PaddleGlobal> {
  if (!ready) {
    ready = loadScript().then(() => {
      const paddle = window.Paddle as PaddleGlobal;
      if (config.environment === "sandbox") paddle.Environment.set("sandbox");
      paddle.Initialize({
        token: config.client_token,
        eventCallback: (event) => {
          if (event.name === "checkout.completed" && onCompleted) onCompleted();
        },
      });
      return paddle;
    });
    ready.catch(() => {
      ready = null;
    });
  }
  return ready;
}

export async function openCheckout(config: PaddleConfig, transactionId: string, locale: string, completed: () => void): Promise<void> {
  const paddle = await initPaddle(config);
  onCompleted = completed;
  paddle.Checkout.open({
    transactionId,
    settings: { displayMode: "overlay", variant: "one-page", theme: "dark", locale },
  });
}
