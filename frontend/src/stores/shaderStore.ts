import { create } from "zustand";

interface ShaderState {
  boostToken: number;
  triggerBoost: () => void;
}

export const useShaderStore = create<ShaderState>((set) => ({
  boostToken: 0,
  triggerBoost: () => set((s) => ({ boostToken: s.boostToken + 1 })),
}));
