import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

interface Props {
  title: string;
  updated: string;
  children: React.ReactNode;
}

export default function LegalLayout({ title, updated, children }: Props) {
  return (
    <div className="min-h-screen bg-ink-950">
      <header className="border-b border-white/5 bg-ink-950/90 backdrop-blur-xl sticky top-0 z-30">
        <div className="max-w-3xl mx-auto px-6 h-12 flex items-center justify-between">
          <Link to="/" className="font-display text-lg text-ink-50 leading-none">
            Proof<span className="italic text-iris">Layer</span>
          </Link>
          <Link to="/" className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500 hover:text-ink-200 transition">
            <ArrowLeft size={11} strokeWidth={1.5} /> Home
          </Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-12">
        <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-ink-600 mb-4">Legal</div>
        <h1 className="font-display text-3xl text-ink-50 mb-2">{title}</h1>
        <p className="font-mono text-[10px] text-ink-600 mb-10">Last updated: {updated}</p>

        <div className="space-y-8 font-mono text-[13px] text-ink-300 leading-relaxed">
          {children}
        </div>

        <div className="mt-14 pt-6 border-t border-white/5 flex flex-wrap gap-x-6 gap-y-2 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-700">
          <Link to="/pricing" className="hover:text-ink-400 transition">Pricing</Link>
          <Link to="/terms" className="hover:text-ink-400 transition">Terms</Link>
          <Link to="/privacy" className="hover:text-ink-400 transition">Privacy</Link>
          <Link to="/refund" className="hover:text-ink-400 transition">Refund</Link>
          <a href="mailto:hello@prooflayer.cloud" className="hover:text-ink-400 transition">Contact</a>
        </div>
      </main>
    </div>
  );
}
