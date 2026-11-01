import { createContext, useContext, useEffect, useMemo, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, request, setActiveOrganizationId, setCsrfToken } from "./api";

const SESSION_KEY = ["auth-session"];

export type AuthUser = {
  id: number;
  email: string;
  email_verified: boolean;
};

export type OrganizationMembership = {
  organization_id: number;
  organization_name: string;
  role: string;
  is_demo?: boolean;
};

export type AuthSession = {
  user: AuthUser | null;
  memberships: OrganizationMembership[];
  active_organization_id: number | null;
  csrf_token?: string | null;
};

type Credentials = { email: string; password: string };
type Registration = Credentials & { organization_name: string };

type AuthContextValue = {
  session: AuthSession | null;
  isLoading: boolean;
  error: string | null;
  login: (credentials: Credentials) => Promise<void>;
  register: (registration: Registration) => Promise<void>;
  logout: () => Promise<void>;
  selectOrganization: (organizationId: number) => Promise<void>;
};

async function authRequest<T>(path: string, init?: RequestInit): Promise<T> {
  return request<T>(path, init);
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  useEffect(() => {
    const handleExpiredSession = () => queryClient.setQueryData(SESSION_KEY, null);
    window.addEventListener("vantage-auth-expired", handleExpiredSession);
    return () => window.removeEventListener("vantage-auth-expired", handleExpiredSession);
  }, [queryClient]);
  const sessionQuery = useQuery({
    queryKey: SESSION_KEY,
    queryFn: async () => {
      try {
        return await authRequest<AuthSession>("/auth/me");
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    retry: false,
    staleTime: 30_000,
  });
  const session = sessionQuery.data ?? null;
  setActiveOrganizationId(session?.active_organization_id ?? null);
  setCsrfToken(session?.csrf_token ?? null);
  const loginMutation = useMutation({
    mutationFn: (credentials: Credentials) => authRequest("/auth/login", { method: "POST", body: JSON.stringify(credentials) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: SESSION_KEY }),
  });
  const registerMutation = useMutation({
    mutationFn: (payload: Registration) => authRequest("/auth/register", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: SESSION_KEY }),
  });
  const logoutMutation = useMutation({
    mutationFn: () => authRequest("/auth/logout", { method: "POST" }),
    onSuccess: () => queryClient.setQueryData(SESSION_KEY, null),
  });
  const organizationMutation = useMutation({
    mutationFn: (organizationId: number) => authRequest(`/organizations/${organizationId}/switch`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: SESSION_KEY }),
  });

  const value = useMemo<AuthContextValue>(() => ({
    session,
    isLoading: sessionQuery.isPending || sessionQuery.isRefetching,
    error: sessionQuery.error?.message ?? null,
    login: async (credentials) => { await loginMutation.mutateAsync(credentials); },
    register: async (registration) => { await registerMutation.mutateAsync(registration); },
    logout: async () => { await logoutMutation.mutateAsync(); },
    selectOrganization: async (organizationId) => { await organizationMutation.mutateAsync(organizationId); },
  }), [sessionQuery.data, sessionQuery.isPending, sessionQuery.isRefetching, sessionQuery.error, loginMutation, registerMutation, logoutMutation, organizationMutation]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider.");
  return context;
}
