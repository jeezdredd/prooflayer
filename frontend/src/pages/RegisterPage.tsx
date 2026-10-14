import { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { useRegister } from "../hooks/useAuth";
import ShaderBackground from "../components/ui/ShaderBackground";
import { AGE_HINT, AGE_LABEL, legalHref } from "../legal";
import LangSwitch from "../components/LangSwitch";
import { t } from "../i18n";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [isAdult, setIsAdult] = useState(false);
  const [allowTraining, setAllowTraining] = useState(true);
  const register = useRegister();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!acceptTerms) return;
    register.mutate({
      email,
      username,
      password,
      password_confirm: passwordConfirm,
      accept_terms: true,
      is_adult: isAdult,
      allow_training: allowTraining,
    });
  };

  return (
    <div className="min-h-screen flex items-center justify-center text-ink-100 relative overflow-hidden px-6 py-10">
      <ShaderBackground variant="dawn" />
      <LangSwitch className="absolute top-4 right-4 z-20 bg-ink-950/60" />
      <div className="absolute inset-0 -z-10 bg-grid-fine bg-grid-fine opacity-[0.4] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,black,transparent)]" />

      <motion.div
        className="w-full max-w-md relative z-10"
        initial={{ opacity: 0, y: 20, filter: "blur(8px)" }}
        animate={{ opacity: 1, y: 0, filter: "blur(0)" }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
      >
        <Link to="/" className="block mb-10 text-center">
          <motion.span
            className="font-display text-5xl text-white tracking-tight inline-block drop-shadow-[0_2px_24px_rgba(0,0,0,0.6)]"
            whileHover={{ scale: 1.04 }}
            transition={{ type: "spring", stiffness: 300 }}
          >
            Proof<span className="italic text-iris">Layer</span>
          </motion.span>
        </Link>

        <form onSubmit={handleSubmit} className="case-card crop-marks">
          <div className="flex items-center justify-between px-6 py-3 border-b border-[var(--line)]">
            <div className="flex items-center gap-3">
              <span className="relative inline-flex">
                <span className="w-1.5 h-1.5 rounded-full bg-signal-cyan" />
                <motion.span
                  className="absolute inset-0 rounded-full bg-signal-cyan"
                  animate={{ scale: [1, 2.4], opacity: [0.7, 0] }}
                  transition={{ duration: 1.6, repeat: Infinity, ease: "easeOut" }}
                />
              </span>
              <span className="label-mono">{t("Access Request")}</span>
            </div>
            <span className="font-mono text-[10px] text-ink-500">{t("NEW · ID")}</span>
          </div>

          <motion.div
            className="p-6 space-y-4"
            initial="hidden"
            animate="visible"
            variants={{ visible: { transition: { staggerChildren: 0.06, delayChildren: 0.15 } } }}
          >
            {[
              { l: t("Email"), kind: "email", v: email, set: setEmail, ph: "agent@field.org", auto: true },
              { l: t("Username"), kind: "text", v: username, set: setUsername, ph: t("Username") },
              { l: t("Password"), kind: "password", v: password, set: setPassword, ph: t("Min 8 chars") },
              { l: t("Confirm Password"), kind: "password", v: passwordConfirm, set: setPasswordConfirm, ph: "" },
            ].map((f) => (
              <motion.div key={f.l} variants={{ hidden: { opacity: 0, y: 8 }, visible: { opacity: 1, y: 0 } }}>
                <label className="label-mono block mb-2">{f.l}</label>
                <input
                  type={f.kind}
                  value={f.v}
                  onChange={(e) => f.set(e.target.value)}
                  required
                  autoFocus={f.auto}
                  className="input-forensic"
                  placeholder={f.ph}
                />
              </motion.div>
            ))}

            <motion.div variants={{ hidden: { opacity: 0, y: 8 }, visible: { opacity: 1, y: 0 } }} className="space-y-2.5">
              <label className="flex items-start gap-2.5 font-mono text-[11px] text-ink-300 leading-relaxed cursor-pointer">
                <input type="checkbox" checked={acceptTerms} onChange={(e) => setAcceptTerms(e.target.checked)} required className="mt-0.5" />
                <span>
                  {t("I accept the")} <a href={legalHref("/terms")} target="_blank" rel="noopener noreferrer" className="text-signal-amber hover:underline">{t("Terms")}</a>{" "}
                  {t("and have read the")} <a href={legalHref("/privacy")} target="_blank" rel="noopener noreferrer" className="text-signal-amber hover:underline">{t("Privacy Policy")}</a>.
                </span>
              </label>
              <label className="flex items-start gap-2.5 font-mono text-[11px] text-ink-300 leading-relaxed cursor-pointer">
                <input type="checkbox" checked={isAdult} onChange={(e) => setIsAdult(e.target.checked)} className="mt-0.5" />
                <span>
                  {t(AGE_LABEL)}
                  <span className="block text-ink-500">{t(AGE_HINT)}</span>
                </span>
              </label>
              <label className="flex items-start gap-2.5 font-mono text-[11px] text-ink-500 leading-relaxed cursor-pointer">
                <input type="checkbox" checked={allowTraining} onChange={(e) => setAllowTraining(e.target.checked)} className="mt-0.5" />
                <span>{t("Help improve detection: let ProofLayer use reviewed copies of my personal uploads to train its detectors. On by default; untick to opt out, or turn it off any time in your account. Never class work.")}</span>
              </label>
            </motion.div>

            {register.isError && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1, x: [0, -8, 8, -8, 8, 0] }}
                transition={{ duration: 0.5 }}
                className="flex items-center gap-2 p-3 border border-signal-blood bg-signal-blood/5"
              >
                <span className="w-4 h-4 border border-signal-blood text-signal-blood text-[10px] font-bold flex items-center justify-center">!</span>
                <span className="font-mono text-[11px] text-signal-blood">{t("Registration rejected. Check inputs.")}</span>
              </motion.div>
            )}

            <motion.button
              variants={{ hidden: { opacity: 0, y: 8 }, visible: { opacity: 1, y: 0 } }}
              type="submit"
              disabled={register.isPending || !acceptTerms}
              className="btn-forensic w-full justify-center disabled:opacity-40"
              whileTap={{ scale: 0.98 }}
            >
              {register.isPending ? t("Creating account…") : `${t("Create account")} →`}
            </motion.button>
          </motion.div>

          <div className="dot-divider mx-6" />
          <div className="px-6 py-4 text-center font-mono text-[11px] text-ink-500">
            {t("Already have an account?")}{" "}
            <Link to={`/login${window.location.search}`} className="text-signal-cyan hover:underline">
              {t("Sign in")} →
            </Link>
          </div>
        </form>
      </motion.div>
    </div>
  );
}
