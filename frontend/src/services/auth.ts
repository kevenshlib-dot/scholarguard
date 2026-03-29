import client from "./api";

const TOKEN_KEY = "sg_token";
const USER_KEY = "sg_user";

export interface AuthUser {
  id: string;
  username: string;
  email: string;
  role: string;
  organization_name?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

/** Persist token + user and set axios default header */
function persist(token: string, user: AuthUser) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  client.defaults.headers.common["Authorization"] = `Bearer ${token}`;
}

/** Clear stored auth state and remove header */
function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  delete client.defaults.headers.common["Authorization"];
}

export async function login(
  email: string,
  password: string
): Promise<AuthResponse> {
  const { data } = await client.post<AuthResponse>("/auth/login", {
    email,
    password,
  });
  persist(data.access_token, data.user);
  return data;
}

export async function register(
  username: string,
  email: string,
  password: string,
  organizationName?: string
): Promise<AuthResponse> {
  const { data } = await client.post<AuthResponse>("/auth/register", {
    username,
    email,
    password,
    organization_name: organizationName || undefined,
  });
  persist(data.access_token, data.user);
  return data;
}

export function logout() {
  clearAuth();
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  const { data } = await client.get<AuthUser>("/auth/me");
  localStorage.setItem(USER_KEY, JSON.stringify(data));
  return data;
}

export async function refreshToken(): Promise<string> {
  const currentToken = getToken();
  if (!currentToken) throw new Error("No token to refresh");
  const { data } = await client.post<{ access_token: string; token_type: string }>(
    "/auth/refresh",
    { token: currentToken }
  );
  const user = getUser();
  if (user) {
    persist(data.access_token, user);
  }
  return data.access_token;
}

/** Restore Authorization header from localStorage on module load */
export function initAuthHeader() {
  const token = getToken();
  if (token) {
    client.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  }
}
