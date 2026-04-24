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

function loadFromStorage(): Pick<AuthState, "user" | "isAuthenticated"> {
  try {
    const tokens = localStorage.getItem("tokens");
    const userStr = localStorage.getItem("user");
    if (tokens && userStr) {
      return { user: JSON.parse(userStr), isAuthenticated: true };
    }
  } catch {
    // ignore
  }
  return { user: null, isAuthenticated: false };
}

export const useAuthStore = create<AuthState>((set) => ({
  ...loadFromStorage(),

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
    set(loadFromStorage());
  },
}));
