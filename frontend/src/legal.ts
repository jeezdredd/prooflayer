import { IS_CLASSROOM_APP } from "./appMode";

export const TERMS_VERSION = "2026-10-13";

export const VERDICT_DISCLAIMER = "Probabilistic assessment. A person makes the decision.";

export const AGE_LABEL = "I am 18 or older";

export const AGE_HINT = "Under 18? You can use everything except other people's public uploads, which may include adult material.";

export const LEGAL = {
  brand: "ProofLayer",
  operatorName: "",
  operatorRegistration: "",
  operatorAddress: "",
  country: "Republic of Kazakhstan",
  updated: "October 13, 2026",
  emails: {
    legal: "legal@prooflayer.cloud",
    finance: "finance@prooflayer.cloud",
    support: "support@prooflayer.cloud",
    sales: "sales@prooflayer.cloud",
  },
};

export function operatorLine(): string {
  const parts = [LEGAL.operatorName, LEGAL.operatorRegistration, LEGAL.operatorAddress].filter(Boolean);
  return parts.length ? `${parts.join(", ")}, ${LEGAL.country}` : `the operator of ProofLayer, ${LEGAL.country}`;
}

export function legalHref(path: string): string {
  const main: string = import.meta.env.VITE_MAIN_URL || "https://prooflayer.cloud";
  return IS_CLASSROOM_APP ? `${main}${path}` : path;
}
