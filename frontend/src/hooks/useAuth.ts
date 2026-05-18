import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { auth } from "../api/endpoints";
import { useAuthStore } from "../stores/authStore";

export function useLogin() {
  const { setUser, setAccess } = useAuthStore();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (data: { email: string; password: string }) => auth.login(data),
    onSuccess: async (res) => {
      setAccess(res.data.access);
      const me = await auth.me();
      setUser(me.data);
      navigate("/upload");
    },
  });
}

export function useRegister() {
  const { setUser, setAccess } = useAuthStore();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (data: { email: string; username: string; password: string; password_confirm: string }) =>
      auth.register(data),
    onSuccess: (res) => {
      setAccess(res.data.access);
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
