import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { X, MessageSquarePlus, Send, CheckCircle } from "lucide-react";
import clsx from "clsx";
import { feedback } from "../api/endpoints";

const CATEGORIES = [
  { value: "accuracy", label: "Detection Accuracy" },
  { value: "ux", label: "UX / Design" },
  { value: "performance", label: "Performance" },
  { value: "feature_request", label: "Feature Request" },
  { value: "bug", label: "Bug Report" },
  { value: "other", label: "Other" },
];

interface FeedbackModalProps {
  open: boolean;
  onClose: () => void;
}

export function FeedbackModal({ open, onClose }: FeedbackModalProps) {
  const [category, setCategory] = useState("other");
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  const reset = () => {
    setCategory("other");
    setMessage("");
    setEmail("");
    setLoading(false);
    setDone(false);
    setError("");
  };

  const handleClose = () => {
    onClose();
    setTimeout(reset, 300);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim().length < 10) {
      setError("Message must be at least 10 characters.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await feedback.submit({ category, message: message.trim(), contact_email: email.trim() });
      setDone(true);
    } catch {
      setError("Failed to send. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-50 bg-ink-950/70 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={handleClose}
          />
          <motion.div
            className="fixed bottom-6 right-6 z-50 w-[360px] case-card crop-marks shadow-xl"
            initial={{ opacity: 0, y: 16, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.97 }}
            transition={{ type: "spring", stiffness: 320, damping: 26 }}
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-ink-800">
              <div className="flex items-center gap-2">
                <MessageSquarePlus size={14} className="text-iris" strokeWidth={1.5} />
                <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-200">
                  Send Feedback
                </span>
              </div>
              <button
                onClick={handleClose}
                className="text-ink-500 hover:text-ink-100 transition-colors"
              >
                <X size={14} />
              </button>
            </div>

            {done ? (
              <div className="px-5 py-8 flex flex-col items-center gap-3 text-center">
                <CheckCircle size={28} className="text-sage-400" strokeWidth={1.5} />
                <p className="font-mono text-sm text-ink-100">Thank you for the feedback.</p>
                <p className="font-mono text-xs text-ink-500">It helps improve ProofLayer.</p>
                <button
                  onClick={handleClose}
                  className="mt-2 font-mono text-[11px] uppercase tracking-[0.12em] text-iris hover:text-iris-light transition-colors"
                >
                  Close
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="px-4 py-4 space-y-3">
                <div>
                  <label className="block font-mono text-[9px] uppercase tracking-[0.16em] text-ink-500 mb-1">
                    Category
                  </label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full border border-ink-700 px-3 py-2 text-sm font-mono text-ink-100 focus:outline-none focus:border-iris transition appearance-none"
                  style={{ background: "var(--ink-900, #0d0f14)", colorScheme: "dark" }}
                  >
                    {CATEGORIES.map((c) => (
                      <option key={c.value} value={c.value}>{c.label}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block font-mono text-[9px] uppercase tracking-[0.16em] text-ink-500 mb-1">
                    Message *
                  </label>
                  <textarea
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    rows={4}
                    placeholder="Describe the issue or suggestion..."
                    className="w-full border border-ink-700 px-3 py-2 text-sm font-mono text-ink-100 placeholder:text-ink-600 focus:outline-none focus:border-iris transition resize-none appearance-none"
                    style={{ background: "var(--ink-900, #0d0f14)", colorScheme: "dark" }}
                  />
                  <div className="flex justify-between mt-0.5">
                    {error ? (
                      <span className="font-mono text-[10px] text-signal-blood">{error}</span>
                    ) : (
                      <span />
                    )}
                    <span className={clsx("font-mono text-[9px]", message.length < 10 ? "text-ink-600" : "text-ink-400")}>
                      {message.length} / 4000
                    </span>
                  </div>
                </div>

                <div>
                  <label className="block font-mono text-[9px] uppercase tracking-[0.16em] text-ink-500 mb-1">
                    Contact email (optional)
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="w-full border border-ink-700 px-3 py-2 text-sm font-mono text-ink-100 placeholder:text-ink-600 focus:outline-none focus:border-iris transition appearance-none"
                    style={{ background: "var(--ink-900, #0d0f14)", colorScheme: "dark" }}
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading || message.trim().length < 10}
                  className={clsx(
                    "w-full flex items-center justify-center gap-2 py-2.5 font-mono text-[11px] uppercase tracking-[0.14em] border transition",
                    "border-iris/60 text-iris hover:bg-iris/10",
                    (loading || message.trim().length < 10) && "opacity-40 cursor-not-allowed",
                  )}
                >
                  {loading ? (
                    <span className="animate-spin w-3 h-3 border border-iris border-t-transparent rounded-full" />
                  ) : (
                    <Send size={12} strokeWidth={1.5} />
                  )}
                  {loading ? "Sending..." : "Send Feedback"}
                </button>
              </form>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

export function FeedbackTrigger({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      title="Send feedback"
      className="fixed bottom-6 right-6 z-40 flex items-center gap-2 px-3 py-2 bg-ink-950/90 backdrop-blur-sm border border-ink-700 hover:border-iris/60 text-ink-400 hover:text-iris transition-all font-mono text-[10px] uppercase tracking-[0.12em] shadow-lg"
    >
      <MessageSquarePlus size={13} strokeWidth={1.5} />
      Feedback
    </button>
  );
}
