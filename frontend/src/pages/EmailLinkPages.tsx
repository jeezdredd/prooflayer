import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { motion } from "motion/react";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { auth } from "../api/endpoints";
import { refreshSignedInUser } from "../auth/sessionSync";
import { useAuthStore } from "../stores/authStore";
import ShaderBackground from "../components/ui/ShaderBackground";
import { postAuthPath } from "../appMode";
import { t } from "../i18n";

type Status = "pending" | "ok" | "fail";

interface LinkState {
  status: Status;
  message: string;
}

interface LinkTarget {
  to: string;
  label: string;
}

interface ErrorData {
  detail?: string;
  code?: string;
}

const runs = new Map<string, Promise<string>>();

function once(key: string, run: () => Promise<string>): Promise<string> {
  let promise = runs.get(key);
  if (!promise) {
    promise = run();
    runs.set(key, promise);
  }
  return promise;
}

function errorData(err: unknown): ErrorData {
  return (err as { response?: { data?: ErrorData } })?.response?.data ?? {};
}

function useTokenLink(kind: string, run: (token: string) => Promise<string>, failText: (err: unknown) => string, missing: string): LinkState {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [state, setState] = useState<LinkState>(token ? { status: "pending", message: "" } : { status: "fail", message: missing });

  useEffect(() => {
    if (!token) return;
    let live = true;
    once(`${kind}:${token}`, () => run(token)).then(
      (message) => {
        if (live) setState({ status: "ok", message });
      },
      (err) => {
        if (live) setState({ status: "fail", message: failText(err) });
      },
    );
    return () => {
      live = false;
    };
  }, [kind, token, run, failText]);

  return state;
}

interface CardProps {
  state: LinkState;
  pendingText: string;
  okTitle: string;
  failTitle: string;
  okLink: LinkTarget;
  failLink: LinkTarget;
}

function EmailLinkCard({ state, pendingText, okTitle, failTitle, okLink, failLink }: CardProps) {
  return (
    <div className="min-h-screen flex items-center justify-center text-ink-100 relative overflow-hidden px-6">
      <ShaderBackground variant="noir" />
      <motion.div
        className="w-full max-w-md relative z-10 case-card p-10 text-center"
        initial={{ opacity: 0, y: 20, filter: "blur(8px)" }}
        animate={{ opacity: 1, y: 0, filter: "blur(0)" }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      >
        <Link to="/" className="block mb-8 font-display text-3xl text-white">
          ProofLayer
        </Link>
        {state.status === "pending" && (
          <div className="flex flex-col items-center gap-3 text-ink-300">
            <Loader2 className="w-10 h-10 animate-spin" />
            <p>{pendingText}</p>
          </div>
        )}
        {state.status === "ok" && (
          <div className="flex flex-col items-center gap-4">
            <CheckCircle2 className="w-12 h-12 text-sage-400" />
            <h1 className="font-display text-2xl text-white">{okTitle}</h1>
            <p className="text-sm text-ink-400">{state.message}</p>
            <Link
              to={okLink.to}
              className="mt-4 inline-block bg-white text-black px-6 py-2.5 text-sm font-medium hover:bg-ink-200 transition"
            >
              {okLink.label}
            </Link>
          </div>
        )}
        {state.status === "fail" && (
          <div className="flex flex-col items-center gap-4">
            <XCircle className="w-12 h-12 text-blood-500" />
            <h1 className="font-display text-2xl text-white">{failTitle}</h1>
            <p className="text-sm text-ink-400">{state.message}</p>
            <Link
              to={failLink.to}
              className="mt-4 inline-block border border-ink-700 text-ink-200 px-6 py-2.5 text-sm font-medium hover:bg-ink-800 transition"
            >
              {failLink.label}
            </Link>
          </div>
        )}
      </motion.div>
    </div>
  );
}

async function verify(token: string): Promise<string> {
  const res = await auth.verifyEmail(token);
  await refreshSignedInUser();
  return t(res.data.detail);
}

function verifyFailText(err: unknown): string {
  const detail = errorData(err).detail;
  return detail ? t(detail) : t("Verification failed.");
}

export function VerifyEmailPage() {
  const state = useTokenLink("verify", verify, verifyFailText, t("Missing verification token."));
  return (
    <EmailLinkCard
      state={state}
      pendingText={t("Verifying your email...")}
      okTitle={t("Email verified")}
      failTitle={t("Could not verify")}
      okLink={{ to: postAuthPath(), label: t("Continue to ProofLayer") }}
      failLink={{ to: "/login", label: t("Back to login") }}
    />
  );
}

async function confirmChange(token: string): Promise<string> {
  const res = await auth.confirmEmailChange(token);
  await refreshSignedInUser();
  return t("Your account now uses {email}. Sign in with this address from now on.", { email: res.data.email });
}

function confirmFailText(err: unknown): string {
  const { code, detail } = errorData(err);
  switch (code) {
    case "expired":
      return t("This link has expired. Ask for a new one on your account page.");
    case "used":
      return t("This link was already used. If your address did not change, ask for a new link on your account page.");
    case "cancelled":
      return t("This link no longer works: the change was cancelled or a newer link was sent. Open the newest email.");
    case "email_taken":
      return t("Another account started using this address in the meantime. Choose a different one on your account page.");
    case "invalid":
      return t("This link is not valid. Check that you opened the whole link from the email.");
    default:
      return detail ? t(detail) : t("Could not change the email. Try again later.");
  }
}

export function ConfirmEmailPage() {
  const signedIn = useAuthStore((s) => s.isAuthenticated);
  const state = useTokenLink(
    "confirm-email",
    confirmChange,
    confirmFailText,
    t("This link is not valid. Check that you opened the whole link from the email."),
  );
  const next = signedIn ? { to: "/account", label: t("Open your account") } : { to: "/login", label: t("Sign in") };
  return (
    <EmailLinkCard
      state={state}
      pendingText={t("Changing your email...")}
      okTitle={t("Email changed")}
      failTitle={t("Could not change the email")}
      okLink={next}
      failLink={next}
    />
  );
}
