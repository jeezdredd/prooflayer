export const CLASSROOM_URL: string = import.meta.env.VITE_CLASSROOM_URL || "https://classroom.prooflayer.cloud";

export const IS_CLASSROOM_APP: boolean =
  typeof window !== "undefined" &&
  (window.location.hostname.startsWith("classroom.") || import.meta.env.VITE_APP_MODE === "classroom");

export function safeNext(raw: string | null): string | null {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.includes("\\")) return null;
  return raw;
}

export function postAuthPath(): string {
  const next = safeNext(new URLSearchParams(window.location.search).get("next"));
  return next ?? (IS_CLASSROOM_APP ? "/" : "/upload");
}
