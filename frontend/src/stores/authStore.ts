import { create } from "zustand";
import type { User } from "../types";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  setUser: (user: User) => void;
  setTokens: (access: string, refresh: string) => void;
  logout: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,

  setUser: (user) => {
    localStorage.setItem("user", JSON.stringify(user));
    set({ user, isAuthenticated: true });
  },

  setTokens: (access, refresh) => {
    localStorage.setItem("tokens", JSON.stringify({ access, refresh }));
  },

  logout: () => {
    localStorage.removeItem("tokens");
    localStorage.removeItem("user");
    set({ user: null, isAuthenticated: false });
  },

  hydrate: () => {
    const tokens = localStorage.getItem("tokens");
    const userStr = localStorage.getItem("user");
    if (tokens && userStr) {
      set({ user: JSON.parse(userStr), isAuthenticated: true });
    }
  },
}));
