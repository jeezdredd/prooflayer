import { IS_CLASSROOM_APP } from "./appMode";
import { currentLang, msg } from "./i18n";

export const TERMS_VERSION = "2026-10-13";

export const VERDICT_DISCLAIMER = msg("Probabilistic assessment. A person makes the decision.");

export const AGE_LABEL = msg("I am 18 or older");

export const AGE_HINT = msg("Under 18? You can use everything except other people's public uploads, which may include adult material.");

export const LEGAL = {
  brand: "ProofLayer",
  operatorName: "",
  operatorRegistration: "",
  operatorAddress: "",
  country: "Republic of Kazakhstan",
  countryRu: "Республика Казахстан",
  updated: "October 26, 2026",
  updatedRu: "26 октября 2026 г.",
  emails: {
    legal: "legal@prooflayer.cloud",
    finance: "finance@prooflayer.cloud",
    support: "support@prooflayer.cloud",
    sales: "sales@prooflayer.cloud",
  },
};

export function operatorLine(): string {
  const ru = currentLang() === "ru";
  const country = ru ? LEGAL.countryRu : LEGAL.country;
  const parts = [LEGAL.operatorName, LEGAL.operatorRegistration, LEGAL.operatorAddress].filter(Boolean);
  if (parts.length) return `${parts.join(", ")}, ${country}`;
  return ru ? `ProofLayer (автоматические ИИ-системы под надзором человека, ${country})` : `ProofLayer (automated AI systems under human supervision, ${country})`;
}

export function legalUpdated(): string {
  return currentLang() === "ru" ? LEGAL.updatedRu : LEGAL.updated;
}

export function legalHref(path: string): string {
  const main: string = import.meta.env.VITE_MAIN_URL || "https://prooflayer.cloud";
  return IS_CLASSROOM_APP ? `${main}${path}` : path;
}
