export type UserClaims = {
  sub: string;
  name?: string;
  admin?: boolean;
  iat: number;
  exp?: number;
};

let currentUser: UserClaims | null = null;
const subscribers = new Set<(user: UserClaims | null) => void>();

function notify(user: UserClaims | null) {
  for (const fn of subscribers) fn(user);
}

export function subscribeAuth(listener: (user: UserClaims | null) => void) {
  subscribers.add(listener);
  return () => subscribers.delete(listener);
}

export function getCurrentUser(): UserClaims | null {
  return currentUser;
}

export function setCurrentUser(user: UserClaims | null) {
  currentUser = user;
  notify(currentUser);
}

export function decodeJwt(token: string): any {
  try {
    const parts = token.split(".");
    if (parts.length < 2) throw new Error("Invalid token");
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => `%${("00" + c.charCodeAt(0).toString(16)).slice(-2)}`)
        .join("")
    );
    return JSON.parse(jsonPayload);
  } catch (e) {
    return null;
  }
}

export async function adoptToken(token: string): Promise<UserClaims> {
  const res = await fetch(`/auth/adopt`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
    credentials: "include", // important: receive/set HttpOnly cookie
  });
  if (!res.ok) {
    throw new Error(`Adopt token failed: ${res.status}`);
  }
  const data = await res.json();
  const user: UserClaims = data.user;
  setCurrentUser(user);
  return user;
}

export async function getMe(): Promise<UserClaims | null> {
  const res = await fetch(`/auth/me`, {
    method: "GET",
    credentials: "include",
  });
  if (!res.ok) return null;
  const data = await res.json();
  setCurrentUser(data as UserClaims);
  return data as UserClaims;
}

export async function logout(): Promise<void> {
  await fetch(`/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
  setCurrentUser(null);
}

export async function fetchWithAuth(input: RequestInfo | URL, init: RequestInit = {}) {
  const res = await fetch(input, { ...init, credentials: "include" });
  return res;
}
