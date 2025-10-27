export const API_HTTP_URL = import.meta.env.VITE_API_HTTP_URL || "http://localhost:8000";
export const API_WS_URL = import.meta.env.VITE_API_WS_URL || `${API_HTTP_URL.replace(/^http/, "ws")}/ws/chat`;

// Stage Project API Configuration
export const STAGE_API_BASE_URL = import.meta.env.VITE_STAGE_API_BASE_URL || "https://stage-project.simpo.ai";

// Get staff and business details dynamically from postMessage/localStorage (set by parent wrapper)
// Note: Hardcoded fallbacks are intentionally commented out to avoid accidental misuse
// const DEFAULT_MEMBER_ID = '...';
// const DEFAULT_BUSINESS_ID = '...';

// --- Helpers to normalize UUID formats coming from wrappers ---
function safeAtobToBytes(b64: string): Uint8Array | null {
  try {
    // Browser path
    if (typeof atob === 'function') {
      const bin = atob(b64);
      const out = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i) & 0xff;
      return out;
    }
    // Node/test path
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Buf: any = (globalThis as any).Buffer;
    if (Buf) return new Uint8Array(Buf.from(b64, 'base64'));
  } catch {}
  return null;
}

function toHex(num: bigint, width: number): string {
  const s = num.toString(16);
  return s.length >= width ? s : '0'.repeat(width - s.length) + s;
}

function javaLegacyBytesToUuid(bytes: Uint8Array): string | null {
  if (!(bytes && bytes.length === 16)) return null;
  let msb = 0n;
  let lsb = 0n;
  for (let i = 0; i < 8; i++) msb = (msb << 8n) | BigInt(bytes[i]);
  for (let i = 8; i < 16; i++) lsb = (lsb << 8n) | BigInt(bytes[i]);

  const time_low = (msb >> 32n) & 0xffffffffn;
  const time_mid = (msb >> 16n) & 0xffffn;
  const time_hi_version = msb & 0xffffn;
  const clock_seq_hi_variant = (lsb >> 56n) & 0xffn;
  const clock_seq_low = (lsb >> 48n) & 0xffn;
  const node = lsb & 0xffffffffffffn; // 48 bits

  const part4 = (clock_seq_hi_variant << 8n) | clock_seq_low; // 2 bytes

  return [
    toHex(time_low, 8),
    toHex(time_mid, 4),
    toHex(time_hi_version, 4),
    toHex(part4, 4),
    toHex(node, 12),
  ].join('-');
}

function maybeDecodeBinaryCreateFromBase64(input: string): string | null {
  const m = input.match(/Binary\.createFromBase64\('\s*([^'\s]+)\s*',\s*3\s*\)/i);
  if (!m) return null;
  const b = safeAtobToBytes(m[1]);
  if (!b) return null;
  return javaLegacyBytesToUuid(b);
}

function maybeDecodeBase64Uuid(input: string): string | null {
  // Try raw base64 that decodes to 16 bytes
  const b = safeAtobToBytes(input.trim());
  if (!b || b.length !== 16) return null;
  return javaLegacyBytesToUuid(b);
}

function isCanonicalUuid(v: string): boolean {
  return /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/.test(v.trim());
}

export const getMemberId = () => {
  const stored = localStorage.getItem('staffId');
  if (!stored) return '';
  // Support values sent as JSON strings (e.g., '"uuid"')
  try {
    const parsed = JSON.parse(stored);
    if (typeof parsed === 'string') return parsed.trim();
  } catch {}
  return stored.trim();
};

export const getBusinessId = () => {
  // 1) Prefer explicit 'businessId' key from wrapper
  const direct = localStorage.getItem('businessId');
  if (direct && direct.trim()) {
    try {
      const parsed = JSON.parse(direct);
      if (typeof parsed === 'string' && parsed.trim()) {
        const s = parsed.trim();
        const c1 = maybeDecodeBinaryCreateFromBase64(s);
        if (c1) return c1;
        const c2 = maybeDecodeBase64Uuid(s);
        if (c2) return c2;
        if (isCanonicalUuid(s)) return s;
      }
    } catch {
      const s = direct.trim();
      const c1 = maybeDecodeBinaryCreateFromBase64(s);
      if (c1) return c1;
      const c2 = maybeDecodeBase64Uuid(s);
      if (c2) return c2;
      if (isCanonicalUuid(s)) return s;
    }
  }

  // 2) Otherwise, parse from 'bDetails' payload provided by wrapper
  const raw = localStorage.getItem('bDetails');
  if (raw) {
    try {
      const parsed = JSON.parse(raw);
      let candidate: any = (
        parsed?.businessId ||
        parsed?.id ||
        parsed?.business_id ||
        parsed?.business?.id ||
        parsed?.business?._id ||
        parsed?.organizationId ||
        parsed?.orgId
      );
      if (typeof candidate === 'string') {
        const s = candidate.trim();
        const c1 = maybeDecodeBinaryCreateFromBase64(s);
        if (c1) return c1;
        const c2 = maybeDecodeBase64Uuid(s);
        if (c2) return c2;
        if (isCanonicalUuid(s)) return s;
      }
      // Some wrappers may send a plain string in bDetails
      if (typeof parsed === 'string') {
        const s = parsed.trim();
        const c1 = maybeDecodeBinaryCreateFromBase64(s);
        if (c1) return c1;
        const c2 = maybeDecodeBase64Uuid(s);
        if (c2) return c2;
        if (isCanonicalUuid(s)) return s;
      }
    } catch {
      // Some wrappers may send businessId as a simple string in bDetails; try to decode
      const s = raw.trim();
      const c1 = maybeDecodeBinaryCreateFromBase64(s);
      if (c1) return c1;
      const c2 = maybeDecodeBase64Uuid(s);
      if (c2) return c2;
      if (isCanonicalUuid(s)) return s;
    }
  }
  return '';
};

export const getStaffType = () => {
  return localStorage.getItem('staffType') || import.meta.env.VITE_STAFF_TYPE || '';
};

export const getStaffName = () => {
  return localStorage.getItem('staffName') || import.meta.env.VITE_STAFF_NAME || '';
};

export const getBusinessDetails = () => {
  const fromStorage = localStorage.getItem('bDetails');
  if (fromStorage) {
    try {
      return JSON.parse(fromStorage);
    } catch {
      return { id: fromStorage };
    }
  }
  return null;
};

