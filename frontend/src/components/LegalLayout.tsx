import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import LangSwitch from "./LangSwitch";
import { currentLang, t } from "../i18n";

interface Props {
  title: string;
  updated: string;
  children: React.ReactNode;
}

export default function LegalLayout({ title, updated, children }: Props) {
  return (
    <div className="min-h-screen bg-ink-950">
      <header className="border-b border-white/5 bg-ink-950/50 backdrop-blur-xl sticky top-0 z-30">
        <div className="max-w-3xl mx-auto px-6 h-12 flex items-center justify-between">
          <Link to="/" className="font-display text-lg text-ink-50 leading-none">
            Proof<span className="italic text-iris">Layer</span>
          </Link>
          <div className="flex items-center gap-4">
            <LangSwitch />
            <Link to="/" className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500 hover:text-ink-200 transition">
              <ArrowLeft size={11} strokeWidth={1.5} /> {t("Home")}
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-12">
        <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-ink-600 mb-4">{t("Legal")}</div>
        <h1 className="font-display text-3xl text-ink-50 mb-2">{title}</h1>
        <p className="font-mono text-[10px] text-ink-600 mb-10">{t("Last updated: {date}", { date: updated })}</p>
        {currentLang() === "ru" && (
          <p className="font-mono text-[11px] text-ink-500 border border-white/10 px-3 py-2 -mt-6 mb-10">
            {t("This translation is provided for convenience. If the Russian and English texts differ, the English version applies.")}
          </p>
        )}

        <div className="space-y-8 font-mono text-[13px] text-ink-300 leading-relaxed">
          {children}
        </div>

        <div className="mt-14 pt-6 border-t border-white/5 flex flex-wrap gap-x-6 gap-y-2 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-700">
          <Link to="/pricing" className="hover:text-ink-400 transition">{t("Pricing")}</Link>
          <Link to="/terms" className="hover:text-ink-400 transition">{t("Terms")}</Link>
          <Link to="/privacy" className="hover:text-ink-400 transition">{t("Privacy")}</Link>
          <Link to="/refund" className="hover:text-ink-400 transition">{t("Refund Policy")}</Link>
          <Link to="/data-processing" className="hover:text-ink-400 transition">{t("Data processing")}</Link>
          <a href="mailto:hello@prooflayer.cloud" className="hover:text-ink-400 transition">{t("Contact")}</a>
        </div>
      </main>
    </div>
  );
}
