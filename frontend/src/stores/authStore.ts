import { create } from "zustand";
import type { User } from "../types";
import { setAccessToken, getAccessToken } from "../api/client";
import { useUploadStore } from "./uploadStore";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  setUser: (user: User) => void;
  setAccess: (access: string) => void;
  logout: () => void;
  hydrate: () => void;
}

function loadFromStorage(): Pick<AuthState, "user" | "isAuthenticated"> {
  try {
    const access = getAccessToken();
    const userStr = localStorage.getItem("user");
    if (access && userStr) {
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

  setAccess: (access) => {
    setAccessToken(access);
    set({ isAuthenticated: true });
  },

  logout: () => {
    setAccessToken(null);
    localStorage.removeItem("user");
    useUploadStore.getState().reset();
    set({ user: null, isAuthenticated: false });
  },

  hydrate: () => {
    set(loadFromStorage());
  },
}));
