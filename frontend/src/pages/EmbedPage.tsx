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

  const apiBase = import.meta.env.VITE_API_URL || "https://prooflayer.app/api/v1";
  const origin = typeof window !== "undefined" ? window.location.origin : "https://prooflayer.app";
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
        <h1 className="text-2xl font-bold text-gray-900">Embed Badge</h1>
        <p className="text-sm text-gray-500 mt-1">
          Drop a verification badge anywhere. Visitors see ProofLayer verdict for the file matching the given SHA-256.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label className="block">
            <span className="text-xs text-gray-500 uppercase tracking-wide">SHA-256 of file</span>
            <input
              type="text"
              value={sha}
              onChange={(e) => setSha(e.target.value.trim())}
              className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-xs font-mono bg-white"
              placeholder="64-char hex"
            />
          </label>

          <div className="mt-4 relative">
            <pre className="bg-gray-900 text-gray-100 text-xs p-4 rounded-lg overflow-x-auto">
              {snippet}
            </pre>
            <button
              onClick={copy}
              className="absolute top-2 right-2 px-2 py-1 bg-gray-700 hover:bg-gray-600 text-white text-xs rounded"
            >
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>

          <div className="mt-4 text-xs text-gray-500 space-y-2">
            <p>
              <span className="font-semibold text-gray-700">How it works.</span> Widget hits{" "}
              <code className="bg-gray-100 px-1 rounded">{apiBase}/content/widget/embed/&lt;sha&gt;/</code>,
              renders verdict pill inline. No auth needed, CORS open.
            </p>
            <p>
              <span className="font-semibold text-gray-700">Use case.</span> News sites, social
              platforms, journalists. Anyone hosting media can certify it without server work.
            </p>
          </div>
        </div>

        <div>
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-2">Live preview</div>
          <div className="bg-white border border-gray-200 rounded-xl p-6 min-h-[120px] flex items-center justify-center animate-fade-in-up">
            <div ref={previewRef} />
          </div>
          <div className="mt-3 text-xs text-gray-400">
            Tip: paste a real SHA-256 from your dashboard to see it light up.
          </div>
        </div>
      </div>
    </div>
  );
}
