import { useEffect } from "react";
import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL || "/api/v1";
const KEY = "prooflayer.visit.tracked";

export function useVisitTracking() {
  useEffect(() => {
    if (sessionStorage.getItem(KEY)) return;
    sessionStorage.setItem(KEY, "1");

    const payload = {
      path: window.location.pathname,
      referrer: document.referrer || "",
    };

    axios
      .post(`${API_URL}/system/visit/`, payload, { timeout: 5000 })
      .catch(() => {
        sessionStorage.removeItem(KEY);
      });
  }, []);
}
