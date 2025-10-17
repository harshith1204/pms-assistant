type TokenChangeListener = (token: string | null) => void;

const listeners = new Set<TokenChangeListener>();

// Memory-only token. Do not persist to storage.
let cachedToken: string | null = null;

export function getToken(): string | null {
  return cachedToken;
}

export function setToken(token: string): void {
  const next = token?.trim() || "";
  cachedToken = next.length > 0 ? next : null;
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
