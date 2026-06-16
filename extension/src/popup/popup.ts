const API_BASE = "https://prooflayer.com/api/v1";
const POLL_INTERVAL = 2000;

type State = "idle" | "analyzing" | "result" | "limit";

function show(state: State) {
  (["idle", "analyzing", "result", "limit"] as const).forEach((s) => {
    const el = document.getElementById(`state-${s}`);
    if (el) el.hidden = s !== state;
  });
}

function formatVerdict(v: string): string {
  return v.replace(/_/g, " ");
}

function renderResult(data: { final_verdict: string; final_score: number; id: string }) {
  const badge = document.getElementById("verdict-badge")!;
  badge.className = `verdict-badge verdict-${data.final_verdict}`;
  badge.textContent = formatVerdict(data.final_verdict);

  const bar = document.getElementById("score-bar") as HTMLElement;
  bar.style.width = `${Math.round((data.final_score ?? 0) * 100)}%`;

  const meta = document.getElementById("result-meta")!;
  meta.textContent = `Confidence: ${Math.round((data.final_score ?? 0) * 100)}%`;

  const link = document.getElementById("result-link") as HTMLAnchorElement;
  link.href = `https://prooflayer.com/result/${data.id}`;

  show("result");
}

async function poll(submissionId: string): Promise<void> {
  const { pl_token: token } = await chrome.storage.local.get("pl_token");
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const url = `${API_BASE}/content/submissions/${submissionId}/`;

  let attempts = 0;
  const MAX_ATTEMPTS = 60;

  const check = async (): Promise<void> => {
    if (attempts >= MAX_ATTEMPTS) {
      show("idle");
      return;
    }
    attempts++;
    const res = await fetch(url, { headers });
    if (!res.ok) return;
    const data = await res.json();
    if (data.status === "completed") {
      renderResult(data);
      return;
    }
    if (data.status === "failed") {
      show("idle");
      return;
    }
    await new Promise((r) => setTimeout(r, POLL_INTERVAL));
    return check();
  };

  return check();
}

async function analyze(imageUrl: string) {
  show("analyzing");

  const response = await new Promise<{ submission_id?: string; error?: string; status?: number }>(
    (resolve) => chrome.runtime.sendMessage({ type: "ANALYZE_URL", url: imageUrl }, resolve)
  );

  if (!response) {
    show("idle");
    return;
  }

  if (response.status === 429 || response.error === "anonymous_limit_reached") {
    show("limit");
    return;
  }

  if (response.error || !response.submission_id) {
    show("idle");
    return;
  }

  await poll(response.submission_id);
}

document.getElementById("btn-check-again")?.addEventListener("click", () => show("idle"));

document.getElementById("btn-login")?.addEventListener("click", () => {
  chrome.tabs.create({ url: "https://prooflayer.com/login" });
});

chrome.storage.local.get("pl_pending_url", async ({ pl_pending_url }) => {
  if (pl_pending_url) {
    await chrome.storage.local.remove("pl_pending_url");
    await analyze(pl_pending_url);
  }
});

chrome.storage.local.get("pl_pending_result", async ({ pl_pending_result }) => {
  if (pl_pending_result) {
    await chrome.storage.local.remove("pl_pending_result");
    if (pl_pending_result.status === 429 || pl_pending_result.error === "anonymous_limit_reached") {
      show("limit");
    } else if (pl_pending_result.submission_id) {
      show("analyzing");
      await poll(pl_pending_result.submission_id);
    } else {
      show("idle");
    }
  }
});
