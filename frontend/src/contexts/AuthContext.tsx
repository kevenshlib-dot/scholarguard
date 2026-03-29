import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import { useNavigate } from "react-router-dom";
import {
  login as authLogin,
  register as authRegister,
  logout as authLogout,
  getToken,
  getUser,
  fetchCurrentUser,
  initAuthHeader,
  type AuthUser,
} from "../services/auth";

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    username: string,
    email: string,
    password: string,
    orgName?: string
  ) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  // On mount: restore from localStorage and validate
  useEffect(() => {
    initAuthHeader();
    const storedToken = getToken();
    const storedUser = getUser();

    if (storedToken && storedUser) {
      setToken(storedToken);
      setUser(storedUser);

      // Validate token with /auth/me
      fetchCurrentUser()
        .then((freshUser) => {
          setUser(freshUser);
        })
        .catch(() => {
          // Token expired / invalid
          authLogout();
          setToken(null);
          setUser(null);
          navigate("/login", { replace: true });
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const login = useCallback(
    async (email: string, password: string) => {
      const resp = await authLogin(email, password);
      setToken(resp.access_token);
      setUser(resp.user);
    },
    []
  );

  const register = useCallback(
    async (
      username: string,
      email: string,
      password: string,
      orgName?: string
    ) => {
      const resp = await authRegister(username, email, password, orgName);
      setToken(resp.access_token);
      setUser(resp.user);
    },
    []
  );

  const logout = useCallback(() => {
    authLogout();
    setToken(null);
    setUser(null);
    navigate("/login", { replace: true });
  }, [navigate]);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token,
        loading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
