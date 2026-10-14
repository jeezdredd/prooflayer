import { useState } from "react";
import clsx from "clsx";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Send } from "lucide-react";
import client from "../api/client";
import { locale, msg, t } from "../i18n";

interface EmailTestState {
  configured: boolean;
  kinds: string[];
  to: string;
  language: string;
  recent: { at: string; kind: string; to: string; status: string; error: string }[];
}

const KIND_LABELS: Record<string, string> = {
  verify: msg("Confirm email"),
  password_reset: msg("Password reset"),
  objection: msg("Objection"),
  update: msg("Product update"),
};

const STATUS_TONE: Record<string, string> = {
  sent: "text-signal-sage",
  console: "text-signal-amber",
  failed: "text-signal-blood",
};

export default function EmailTestPanel() {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState("verify");
  const { data } = useQuery<EmailTestState>({
    queryKey: ["email-test"],
    queryFn: () => client.get("/auth/email-test/").then((r) => r.data),
  });
  const send = useMutation({
    mutationFn: () => client.post<{ status: string; to: string }>("/auth/email-test/", { kind }).then((r) => r.data),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["email-test"] }),
  });

  if (!data) return null;
  const error = (send.error as { response?: { data?: { error?: string } } } | null)?.response?.data?.error;

  return (
    <div className="px-5 pb-5 pt-1 pl-[3.25rem] space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {data.kinds.map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => setKind(k)}
            className={clsx(
              "rounded-full border px-3 py-1 text-xs transition-colors",
              kind === k ? "border-signal-violet/60 bg-signal-violet/10 text-ink-50" : "border-white/10 text-ink-400 hover:text-ink-100",
            )}
          >
            {t(KIND_LABELS[k] ?? k)}
          </button>
        ))}
        <button
          type="button"
          onClick={() => send.mutate()}
          disabled={send.isPending}
          className="ml-auto inline-flex items-center gap-2 rounded-full border border-signal-amber/50 px-3.5 py-1 text-xs text-signal-amber hover:bg-signal-amber/10 transition-colors disabled:opacity-50"
        >
          <Send size={12} strokeWidth={1.8} />
          {send.isPending ? t("Sending…") : t("Send a test to {email}", { email: data.to })}
        </button>
      </div>
      {send.isSuccess && (
        <div className={clsx("font-mono text-[11px]", STATUS_TONE[send.data.status] ?? "text-ink-300")}>
          {send.data.status === "sent"
            ? t("Sent through Resend. Check {email}.", { email: send.data.to })
            : t("Email is not configured: the message went to the server console.")}
        </div>
      )}
      {send.isError && <div className="font-mono text-[11px] text-signal-blood">{error ?? t("Could not send")}</div>}
      {data.recent.length > 0 && (
        <div className="rounded-xl border border-white/5 divide-y divide-white/5">
          {data.recent.map((row, i) => (
            <div key={i} className="flex items-center gap-3 px-3 py-2 font-mono text-[11px]">
              <span className="text-ink-500 tabular-nums shrink-0">{new Date(row.at).toLocaleString(locale(), { dateStyle: "short", timeStyle: "short" })}</span>
              <span className="text-ink-300 shrink-0">{row.kind}</span>
              <span className="text-ink-500 truncate flex-1" title={row.error || row.to}>{row.to}</span>
              <span className={clsx("shrink-0", STATUS_TONE[row.status] ?? "text-ink-400")}>{row.status}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
