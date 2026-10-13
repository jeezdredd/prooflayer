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
