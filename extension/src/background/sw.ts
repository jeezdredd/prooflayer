const API_BASE = "https://prooflayer.com/api/v1";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "pl-analyze",
    title: "Verify with ProofLayer",
    contexts: ["image"],
  });
});

let pendingImageUrl: string | null = null;

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "SET_IMAGE_URL") {
    pendingImageUrl = msg.url;
  }
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== "pl-analyze") return;
  const url = info.srcUrl ?? pendingImageUrl;
  if (!url || !tab?.id) return;
  chrome.runtime.sendMessage({ type: "ANALYZE_URL", url });
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type !== "ANALYZE_URL") return;

  (async () => {
    const { pl_token: token } = await chrome.storage.local.get("pl_token");
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE}/content/analyze-url/`, {
      method: "POST",
      headers,
      body: JSON.stringify({ url: msg.url }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      sendResponse({ error: err.code ?? err.detail ?? "error", status: res.status });
      return;
    }

    const { submission_id } = await res.json();
    sendResponse({ submission_id });
  })();

  return true;
});
