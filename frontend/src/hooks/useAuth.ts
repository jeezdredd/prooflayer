import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { auth, type RegisterPayload } from "../api/endpoints";
import { useAuthStore } from "../stores/authStore";
import { postAuthPath } from "../appMode";

export function useLogin() {
  const { setUser, setAccess } = useAuthStore();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (data: { email: string; password: string }) => auth.login(data),
    onSuccess: async (res) => {
      setAccess(res.data.access);
      const me = await auth.me();
      setUser(me.data);
      navigate(postAuthPath());
    },
  });
}

export function useRegister() {
  const { setUser, setAccess } = useAuthStore();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (data: RegisterPayload) => auth.register(data),
    onSuccess: (res) => {
      setAccess(res.data.access);
      setUser(res.data.user);
      navigate(postAuthPath());
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
