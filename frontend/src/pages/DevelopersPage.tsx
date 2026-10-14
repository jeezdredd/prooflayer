import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Copy, Check, Trash2, Webhook } from "lucide-react";
import SubscriptionGate from "../components/SubscriptionGate";
import { apiKeys } from "../api/endpoints";
import type { ApiKey, ApiKeyCreated } from "../types";
import { toast } from "../components/ui/Toast";
import { locale, t } from "../i18n";

const API_BASE = import.meta.env.VITE_API_URL || "https://api.prooflayer.cloud/api/v1";

function CopyButton({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setDone(true);
        setTimeout(() => setDone(false), 1400);
      }}
      className="text-ink-400 hover:text-signal-amber transition"
      aria-label={t("Copy")}
    >
      {done ? <Check size={14} /> : <Copy size={14} />}
    </button>
  );
}

function CodeBlock({ title, code }: { title: string; code: string }) {
  return (
    <div className="border border-[var(--line-strong)]">
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--line-strong)]">
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{title}</span>
        <CopyButton text={code} />
      </div>
      <pre className="p-3 overflow-x-auto font-mono text-[12px] leading-relaxed text-ink-200">{code}</pre>
    </div>
  );
}

function NewKeyReveal({ created, onClose }: { created: ApiKeyCreated; onClose: () => void }) {
  return (
    <div className="case-card p-5 mb-6 border border-signal-amber/40">
      <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-signal-amber mb-2">
        {t("Copy now, it will not be shown again")}
      </div>
      <div className="flex items-center gap-3 font-mono text-sm text-ink-50 break-all">
        <span>{created.key}</span>
        <CopyButton text={created.key} />
      </div>
      {created.webhook_secret && (
        <div className="mt-3 flex items-center gap-3 font-mono text-xs text-ink-300 break-all">
          <span className="text-ink-500">{t("webhook secret")}</span>
          <span>{created.webhook_secret}</span>
          <CopyButton text={created.webhook_secret} />
        </div>
      )}
      <button type="button" onClick={onClose} className="mt-4 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-400 hover:text-ink-100">
        {t("I saved it")}
      </button>
    </div>
  );
}

function KeyRow({ apiKey, onRevoke }: { apiKey: ApiKey; onRevoke: (id: number) => void }) {
  const revoked = Boolean(apiKey.revoked_at);
  return (
    <div className={`grid grid-cols-[1fr_auto] md:grid-cols-12 gap-3 items-center py-3 ${revoked ? "opacity-50" : ""}`}>
      <div className="md:col-span-3 text-ink-50">{apiKey.name}</div>
      <div className="md:col-span-3 font-mono text-xs text-ink-300">{apiKey.prefix}…</div>
      <div className="md:col-span-3 font-mono text-[11px] text-ink-500">
        {apiKey.last_used_at ? t("used {date}", { date: new Date(apiKey.last_used_at).toLocaleString(locale()) }) : t("never used")}
      </div>
      <div className="md:col-span-2 font-mono text-[11px] text-ink-500 flex items-center gap-1.5">
        {apiKey.webhook_url ? (
          <>
            <Webhook size={12} />
            {apiKey.last_webhook_status || t("no deliveries")}
          </>
        ) : null}
      </div>
      <div className="md:col-span-1 text-right">
        {revoked ? (
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">{t("revoked")}</span>
        ) : (
          <button type="button" onClick={() => onRevoke(apiKey.id)} className="text-ink-500 hover:text-signal-blood" aria-label={t("Revoke")}>
            <Trash2 size={14} />
          </button>
        )}
      </div>
    </div>
  );
}

function DevelopersInner() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [created, setCreated] = useState<ApiKeyCreated | null>(null);

  const { data: keys = [] } = useQuery({ queryKey: ["api-keys"], queryFn: () => apiKeys.list().then((r) => r.data) });

  const create = useMutation({
    mutationFn: () => apiKeys.create({ name: name.trim(), webhook_url: webhookUrl.trim() }).then((r) => r.data),
    onSuccess: (data) => {
      setCreated(data);
      setName("");
      setWebhookUrl("");
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
    onError: (err: unknown) => {
      const data = (err as { response?: { data?: Record<string, unknown> } })?.response?.data;
      const reason = data?.webhook_url ? String(data.webhook_url) : (data?.detail as string) || "Could not create key";
      toast.error(t(reason));
    },
  });

  const revoke = useMutation({
    mutationFn: (id: number) => apiKeys.revoke(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["api-keys"] }),
  });

  const upload = `curl -X POST ${API_BASE}/content/submissions/ \\
  -H "Authorization: Api-Key $PROOFLAYER_KEY" \\
  -F "file=@photo.jpg"`;
  const poll = `curl ${API_BASE}/content/submissions/<id>/status/ \\
  -H "Authorization: Api-Key $PROOFLAYER_KEY"`;
  const details = `curl ${API_BASE}/content/submissions/<id>/ \\
  -H "Authorization: Api-Key $PROOFLAYER_KEY"`;
  const verify = `import hashlib, hmac

def verify(secret: str, headers: dict, raw_body: bytes) -> bool:
    ts = headers["X-ProofLayer-Timestamp"]
    expected = "sha256=" + hmac.new(secret.encode(), ts.encode() + b"." + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, headers["X-ProofLayer-Signature"])`;

  return (
    <div>
      <div className="mb-6">
        <span className="label-mono">{t("Service / API")}</span>
        <h1 className="font-display text-4xl text-white mt-2">{t("Developers")}</h1>
        <p className="text-sm text-ink-400 mt-2 max-w-2xl">
          {t("Run Tribunal from your own code. Keys act as your account and count against the same monthly quota. Add a webhook URL and we POST the verdict when analysis finishes, so you do not have to poll.")}
        </p>
      </div>

      {created && <NewKeyReveal created={created} onClose={() => setCreated(null)} />}

      <form
        className="case-card p-5 mb-8 grid md:grid-cols-12 gap-3 items-end"
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) create.mutate();
        }}
      >
        <label className="md:col-span-4 block">
          <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{t("Name")}</span>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="newsroom-ci" maxLength={80}
            className="mt-1 w-full bg-transparent border border-[var(--line-strong)] px-3 py-2 text-ink-50 focus:border-signal-amber outline-none" />
        </label>
        <label className="md:col-span-6 block">
          <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{t("Webhook URL (optional, https)")}</span>
          <input value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} placeholder="https://example.com/prooflayer"
            className="mt-1 w-full bg-transparent border border-[var(--line-strong)] px-3 py-2 text-ink-50 focus:border-signal-amber outline-none" />
        </label>
        <button type="submit" disabled={!name.trim() || create.isPending}
          className="md:col-span-2 flex items-center justify-center gap-2 border border-signal-amber/60 text-signal-amber px-3 py-2 font-mono text-[11px] uppercase tracking-[0.14em] hover:bg-signal-amber/10 disabled:opacity-40">
          <KeyRound size={14} /> {t("Create key")}
        </button>
      </form>

      <div className="divide-y divide-[var(--line-strong)] mb-10">
        {keys.length === 0 ? (
          <p className="text-sm text-ink-500 py-4">{t("No keys yet.")}</p>
        ) : (
          keys.map((k) => <KeyRow key={k.id} apiKey={k} onRevoke={(id) => revoke.mutate(id)} />)
        )}
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <CodeBlock title={t("1 · Upload")} code={upload} />
        <CodeBlock title={t("2 · Poll status")} code={poll} />
        <CodeBlock title={t("3 · Full verdict + evidence")} code={details} />
        <CodeBlock title={t("Webhook · verify signature (python)")} code={verify} />
      </div>
      <p className="text-xs text-ink-500 mt-4">
        {t("Rate limit 120 requests/min per key; uploads also follow your plan's hourly upload limit.")}{" "}
        {t("Full schema at")} <a className="underline hover:text-ink-200" href={`${API_BASE.replace(/\/api\/v1$/, "")}/api/docs/`}>/api/docs</a>.
      </p>
    </div>
  );
}

export default function DevelopersPage() {
  return (
    <SubscriptionGate feature="API access">
      <DevelopersInner />
    </SubscriptionGate>
  );
}
