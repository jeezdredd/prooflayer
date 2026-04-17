import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { auth } from "../api/endpoints";
import { useAuthStore } from "../stores/authStore";

export function useLogin() {
  const { setUser, setTokens } = useAuthStore();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (data: { email: string; password: string }) => auth.login(data),
    onSuccess: async (res) => {
      setTokens(res.data.access, res.data.refresh);
      const me = await auth.me();
      setUser(me.data);
      navigate("/upload");
    },
  });
}

export function useRegister() {
  const { setUser, setTokens } = useAuthStore();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (data: { email: string; username: string; password: string; password_confirm: string }) =>
      auth.register(data),
    onSuccess: (res) => {
      setTokens(res.data.tokens.access, res.data.tokens.refresh);
      setUser(res.data.user);
      navigate("/upload");
    },
  });
}

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => auth.me().then((r) => r.data),
    retry: false,
  });
}
