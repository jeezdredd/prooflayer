import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Cookie, X } from "lucide-react";

const KEY = "prooflayer.consent.v1";

export default function ConsentBanner() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(KEY)) setOpen(true);
  }, []);

  const accept = () => {
    localStorage.setItem(KEY, JSON.stringify({ accepted: true, ts: Date.now() }));
    setOpen(false);
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 20 }}
          className="fixed bottom-4 right-4 z-50 max-w-sm case-card p-5"
        >
          <div className="flex items-start gap-3">
            <Cookie className="w-5 h-5 text-signal-amber shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="label-mono mb-1.5">Cookies</div>
              <p className="text-xs text-ink-300 leading-relaxed">
                ProofLayer uses a single strictly-necessary cookie (<span className="font-mono text-ink-200">prooflayer_refresh</span>)
                to keep you signed in. It is httpOnly, secure, SameSite=Lax. No tracking, no analytics, no third parties.
              </p>
              <div className="flex gap-2 mt-3">
                <button
                  onClick={accept}
                  className="font-mono text-[10px] uppercase tracking-[0.14em] border border-iris/60 text-iris hover:bg-iris/10 px-3 py-1.5 transition"
                >
                  Got it
                </button>
              </div>
            </div>
            <button
              onClick={accept}
              className="text-ink-500 hover:text-ink-200 transition"
              aria-label="dismiss"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
