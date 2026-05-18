import { useEffect, useRef, useState } from "react";

const DEFAULT_SHA = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";

function buildSnippet(sha: string, apiBase: string, widgetSrc: string) {
  return `<div data-prooflayer-sha256="${sha}"></div>
<script
  src="${widgetSrc}"
  data-api="${apiBase}"
  async
></script>`;
}

export default function EmbedPage() {
  const [sha, setSha] = useState(DEFAULT_SHA);
  const [copied, setCopied] = useState(false);
  const previewRef = useRef<HTMLDivElement | null>(null);

  const apiBase = import.meta.env.VITE_API_URL || "https://api.prooflayer.cloud/api/v1";
  const origin = typeof window !== "undefined" ? window.location.origin : "https://prooflayer.cloud";
  const widgetSrc = `${origin}/widget.js`;
  const snippet = buildSnippet(sha, apiBase, widgetSrc);

  useEffect(() => {
    if (!previewRef.current) return;
    previewRef.current.innerHTML = "";
    const slot = document.createElement("div");
    slot.setAttribute("data-prooflayer-sha256", sha);
    previewRef.current.appendChild(slot);

    const script = document.createElement("script");
    script.src = widgetSrc;
    script.setAttribute("data-api", apiBase);
    script.async = true;
    previewRef.current.appendChild(script);

    return () => {
      if (previewRef.current) previewRef.current.innerHTML = "";
    };
  }, [sha, apiBase, widgetSrc]);

  const copy = async () => {
    await navigator.clipboard.writeText(snippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div>
      <div className="mb-6">
        <span className="label-mono">Service / 06</span>
        <h1 className="font-display text-4xl text-white mt-2">Embed Badge</h1>
        <p className="text-sm text-ink-400 mt-2">
          Drop a verification badge anywhere. Visitors see ProofLayer verdict for the file matching the given SHA-256.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label className="block">
            <span className="label-mono">SHA-256 of file</span>
            <input
              type="text"
              value={sha}
              onChange={(e) => setSha(e.target.value.trim())}
              className="mt-1 w-full bg-ink-900 border border-ink-700 px-3 py-2 text-xs font-mono text-ink-100 focus:outline-none focus:border-iris transition"
              placeholder="64-char hex"
            />
          </label>

          <div className="mt-4 relative">
            <pre className="bg-black/60 border border-ink-800 text-ink-100 text-xs p-4 overflow-x-auto">
              {snippet}
            </pre>
            <button
              onClick={copy}
              className="absolute top-2 right-2 font-mono text-[10px] uppercase tracking-[0.14em] border border-ink-700 hover:border-iris hover:text-iris text-ink-300 px-2 py-1 transition"
            >
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>

          <div className="mt-4 text-xs text-ink-400 space-y-2">
            <p>
              <span className="font-mono uppercase text-[10px] tracking-[0.14em] text-ink-200">How it works.</span> Widget hits{" "}
              <code className="bg-ink-900 border border-ink-800 text-ink-200 px-1">{apiBase}/content/widget/embed/&lt;sha&gt;/</code>,
              renders verdict pill inline. No auth needed, CORS open.
            </p>
            <p>
              <span className="font-mono uppercase text-[10px] tracking-[0.14em] text-ink-200">Use case.</span> News sites, social
              platforms, journalists. Anyone hosting media can certify it without server work.
            </p>
          </div>
        </div>

        <div>
          <div className="label-mono mb-2">Live preview <span className="text-ink-500 normal-case tracking-normal">- how third-party sites render it</span></div>
          <div className="border border-ink-700 rounded-sm overflow-hidden animate-fade-in-up">
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-ink-900 border-b border-ink-700">
              <span className="w-2 h-2 rounded-full bg-ink-700" />
              <span className="w-2 h-2 rounded-full bg-ink-700" />
              <span className="w-2 h-2 rounded-full bg-ink-700" />
              <span className="font-mono text-[9px] text-ink-500 ml-2">third-party-site.com</span>
            </div>
            <div className="bg-[#f7f8fb] p-6 min-h-[120px] flex items-center justify-center">
              <div ref={previewRef} />
            </div>
          </div>
          <div className="mt-3 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
            Tip: paste a real SHA-256 from your dashboard to see it light up.
          </div>
        </div>
      </div>
    </div>
  );
}
