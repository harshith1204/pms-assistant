type TokenChangeListener = (token: string | null) => void;

const STORAGE_KEY = "jwt";
const listeners = new Set<TokenChangeListener>();

let cachedToken: string | null = null;

function readInitialToken(): string | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && typeof stored === "string" && stored.trim().length > 0) {
      return stored;
    }
  } catch {}
  // Fallback to env-provided token for local/dev if available
  // Note: import.meta.env access is safe in Vite context
  const envToken = (import.meta as any)?.env?.VITE_JWT as string | undefined;
  return envToken && envToken.trim().length > 0 ? envToken : null;
}

cachedToken = readInitialToken();

export function getToken(): string | null {
  return cachedToken;
}

export function setToken(token: string): void {
  const next = token?.trim() || "";
  cachedToken = next.length > 0 ? next : null;
  try {
    if (cachedToken) {
      localStorage.setItem(STORAGE_KEY, cachedToken);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  } catch {}
  for (const fn of listeners) {
    try { fn(cachedToken); } catch {}
  }
}

export function clearToken(): void {
  setToken("");
}

export function subscribe(listener: TokenChangeListener): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
