import { Link, useNavigate } from "react-router-dom";

interface ErrorViewProps {
  code: string;
  label: string;
  title: string;
  message: string;
  accent?: string;
}

function ErrorView({ code, label, title, message, accent = "text-signal-amber" }: ErrorViewProps) {
  const navigate = useNavigate();
  return (
    <div className="min-h-dvh flex items-center justify-center px-6 bg-ink-950">
      <div className="case-card crop-marks p-10 max-w-lg w-full text-center animate-rise">
        <span className="label-mono">Error / {code}</span>
        <div className={`font-display text-7xl lg:text-8xl leading-none mt-4 ${accent}`}>{code}</div>
        <h1 className="font-display text-3xl text-ink-50 mt-4">{title}</h1>
        <p className="text-ink-400 mt-3 leading-relaxed font-mono text-xs uppercase tracking-[0.12em]">{label}</p>
        <p className="text-ink-400 mt-4 leading-relaxed">{message}</p>
        <div className="mt-8 flex items-center justify-center gap-3 flex-wrap">
          <button
            onClick={() => navigate(-1)}
            className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-300 hover:text-signal-amber border border-white/10 hover:border-signal-amber/60 px-4 py-2 rounded-sm transition-colors"
          >
            ← Go Back
          </button>
          <Link to="/" className="btn-forensic">
            Home →
          </Link>
        </div>
      </div>
    </div>
  );
}

export function NotFoundPage() {
  return (
    <ErrorView
      code="404"
      label="Resource not found"
      title="Lost the trail"
      message="This page does not exist or was moved. Check the URL or head back to safety."
    />
  );
}

export function ForbiddenPage() {
  return (
    <ErrorView
      code="403"
      label="Access denied"
      title="Restricted area"
      message="You do not have permission to view this. If you think this is a mistake, contact an administrator."
      accent="text-signal-blood"
    />
  );
}

export function ServerErrorPage({ onReset }: { onReset?: () => void }) {
  return (
    <div className="min-h-dvh flex items-center justify-center px-6 bg-ink-950">
      <div className="case-card crop-marks p-10 max-w-lg w-full text-center animate-rise">
        <span className="label-mono">Error / 500</span>
        <div className="font-display text-7xl lg:text-8xl leading-none mt-4 text-signal-blood">500</div>
        <h1 className="font-display text-3xl text-ink-50 mt-4">Something broke</h1>
        <p className="text-ink-400 mt-3 leading-relaxed font-mono text-xs uppercase tracking-[0.12em]">Internal error</p>
        <p className="text-ink-400 mt-4 leading-relaxed">
          An unexpected error occurred while rendering this view. The team has been notified.
        </p>
        <div className="mt-8 flex items-center justify-center gap-3 flex-wrap">
          <button
            onClick={onReset ?? (() => window.location.reload())}
            className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-300 hover:text-signal-amber border border-white/10 hover:border-signal-amber/60 px-4 py-2 rounded-sm transition-colors"
          >
            ↻ Reload
          </button>
          <a href="/" className="btn-forensic">
            Home →
          </a>
        </div>
      </div>
    </div>
  );
}
