import { create } from "zustand";
import clsx from "clsx";
import { useEffect } from "react";

type ToastKind = "success" | "error" | "info";

interface ToastItem {
  id: string;
  kind: ToastKind;
  message: string;
  ttl: number;
}

interface ToastStore {
  toasts: ToastItem[];
  push: (kind: ToastKind, message: string, ttl?: number) => void;
  dismiss: (id: string) => void;
}

const useToastStore = create<ToastStore>((set, get) => ({
  toasts: [],
  push: (kind, message, ttl = 4000) => {
    const id = Math.random().toString(36).slice(2, 10);
    set({ toasts: [...get().toasts, { id, kind, message, ttl }] });
    if (ttl > 0) {
      setTimeout(() => get().dismiss(id), ttl);
    }
  },
  dismiss: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) }),
}));

export const toast = {
  success: (msg: string, ttl?: number) => useToastStore.getState().push("success", msg, ttl),
  error: (msg: string, ttl?: number) => useToastStore.getState().push("error", msg, ttl),
  info: (msg: string, ttl?: number) => useToastStore.getState().push("info", msg, ttl),
};

const KIND_STYLES: Record<ToastKind, string> = {
  success: "bg-green-50 border-green-200 text-green-900",
  error: "bg-red-50 border-red-200 text-red-900",
  info: "bg-blue-50 border-blue-200 text-blue-900",
};

const KIND_ICONS: Record<ToastKind, string> = {
  success: "✓",
  error: "!",
  info: "i",
};

const KIND_DOT: Record<ToastKind, string> = {
  success: "bg-green-500",
  error: "bg-red-500",
  info: "bg-blue-500",
};

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && toasts.length) dismiss(toasts[toasts.length - 1].id);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toasts, dismiss]);

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={clsx(
            "pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-lg border shadow-lg animate-slide-in-right min-w-[280px] max-w-md",
            KIND_STYLES[t.kind],
          )}
        >
          <div className={clsx("w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0", KIND_DOT[t.kind])}>
            {KIND_ICONS[t.kind]}
          </div>
          <div className="text-sm flex-1">{t.message}</div>
          <button
            onClick={() => dismiss(t.id)}
            className="text-gray-400 hover:text-gray-700 text-lg leading-none"
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
