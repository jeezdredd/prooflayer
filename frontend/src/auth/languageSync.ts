import { useEffect } from "react";
import { auth } from "../api/endpoints";
import { useLangStore } from "../i18n";
import { useAuthStore } from "../stores/authStore";

export function useLanguageSync(): void {
  const lang = useLangStore((s) => s.lang);
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);

  useEffect(() => {
    if (!user || !user.language || user.language === lang) return;
    auth
      .updateMe({ language: lang })
      .then((r) => setUser(r.data))
      .catch(() => undefined);
  }, [lang, user, setUser]);
}
